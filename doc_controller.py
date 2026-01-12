"""
Document Controller for Rice Export FSMS

Implements ISO 22001:2018 Clause 7.5.3 (Control of Documented Information)
Manages document state transitions, version control, and file operations.

Controlled Transition Workflow:
1. Prerequisite Check - Validate doc_id pattern and mandatory metadata
2. System-Driven Renaming - {doc_id}_v{version}_{title_slug}.pdf
3. Read-Only Lock - Set file permissions to prevent editing
4. Hash Integrity Sync - Compute SHA-256 and update database
5. Audit Trail - Log to audit_log.txt
"""

import os
import re
import hashlib
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import httpx

from models import DEPARTMENT_CODES, DOC_TYPE_CODES, VALID_DEPARTMENTS


# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

FOLDERS = {
    "raw": "documents/raw",
    "controlled": "documents/controlled",
    "archive": "documents/archive"
}

AUDIT_LOG_FILE = "audit_log.txt"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ApprovalResult:
    """Result of document approval operation."""
    success: bool
    document_id: int
    doc_id: str
    version: str
    file_path: str
    file_hash: str
    message: str
    errors: list = field(default_factory=list)
    # New fields for enhanced audit trail
    previous_version: str = ""
    approval_timestamp: str = ""
    locked: bool = False
    audit_logged: bool = False


@dataclass
class VersionInfo:
    """Version parsing and manipulation."""
    major: int
    minor: int

    @classmethod
    def parse(cls, version_str: str) -> "VersionInfo":
        """Parse version string like 'v1.0' into VersionInfo."""
        match = re.match(r'^v?(\d+)\.(\d+)$', version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}. Expected v1.0 format.")
        return cls(major=int(match.group(1)), minor=int(match.group(2)))

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}"

    def increment_major(self) -> "VersionInfo":
        """Increment major version (v1.0 → v2.0)."""
        return VersionInfo(major=self.major + 1, minor=0)

    def increment_minor(self) -> "VersionInfo":
        """Increment minor version (v1.0 → v1.1)."""
        return VersionInfo(major=self.major, minor=self.minor + 1)

    def to_first_controlled(self) -> "VersionInfo":
        """Convert to first controlled version (v0.x → v1.0)."""
        return VersionInfo(major=1, minor=0)


# ============================================================================
# File Operations
# ============================================================================

def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA-256 hash of file content.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def sanitize_filename(title: str) -> str:
    """
    Sanitize title for use in filename.

    Args:
        title: Document title

    Returns:
        Sanitized string safe for filenames
    """
    # Replace spaces with underscores
    sanitized = title.replace(" ", "_")
    # Remove special characters, keep only alphanumeric and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)
    # Limit length
    return sanitized[:50]


def generate_controlled_filename(doc_id: str, version: str, title: str, extension: str) -> str:
    """
    Generate controlled document filename.

    Args:
        doc_id: Document ID (e.g., FSMS-SOP-001)
        version: Version string (e.g., v1.0)
        title: Document title
        extension: File extension (e.g., .pdf)

    Returns:
        Formatted filename
    """
    sanitized_title = sanitize_filename(title)
    return f"{doc_id}_{version}_{sanitized_title}{extension}"


def generate_archive_filename(doc_id: str, version: str, extension: str) -> str:
    """
    Generate archive filename for old versions.

    Args:
        doc_id: Document ID
        version: Old version string
        extension: File extension

    Returns:
        Archive filename with date
    """
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{doc_id}_{version}_ARCHIVED_{date_str}{extension}"


def ensure_folders_exist():
    """Create required folder structure if not exists."""
    for folder in FOLDERS.values():
        Path(folder).mkdir(parents=True, exist_ok=True)


def move_to_controlled(source_path: str, doc_id: str, version: str, title: str) -> str:
    """
    Move file from raw to controlled folder with proper naming.

    Args:
        source_path: Path to source file in raw folder
        doc_id: Document ID
        version: Version string
        title: Document title

    Returns:
        New file path in controlled folder
    """
    ensure_folders_exist()

    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    extension = source.suffix
    new_filename = generate_controlled_filename(doc_id, version, title, extension)
    dest_path = Path(FOLDERS["controlled"]) / new_filename

    # Copy file (keep original in raw for safety, can delete later)
    shutil.copy2(source, dest_path)

    return str(dest_path)


def set_readonly(file_path: str):
    """
    Set file to read-only (chmod 444 equivalent).

    Args:
        file_path: Path to file
    """
    # Remove write permissions for owner, group, others
    current_mode = os.stat(file_path).st_mode
    readonly_mode = current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    os.chmod(file_path, readonly_mode)


def archive_old_version(controlled_path: str, doc_id: str, version: str) -> str:
    """
    Move old controlled version to archive.

    Args:
        controlled_path: Path to current controlled file
        doc_id: Document ID
        version: Old version string

    Returns:
        Archive file path
    """
    ensure_folders_exist()

    source = Path(controlled_path)
    if not source.exists():
        return None

    extension = source.suffix
    archive_filename = generate_archive_filename(doc_id, version, extension)
    archive_path = Path(FOLDERS["archive"]) / archive_filename

    # Make file writable before moving (in case it was read-only)
    try:
        os.chmod(source, stat.S_IWUSR | stat.S_IRUSR)
    except:
        pass

    shutil.move(str(source), str(archive_path))

    return str(archive_path)


# ============================================================================
# Audit Logging
# ============================================================================

def log_audit(action: str, doc_id: str, user: str, details: str = ""):
    """
    Log action to audit trail file.

    Args:
        action: Action type (Approved, Version Updated, Status Changed)
        doc_id: Document ID
        user: User who performed action
        details: Additional details
    """
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] {action} | Doc: {doc_id} | User: {user} | {details}\n"

    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(log_entry)


def log_controlled_transition(
    doc_id: str,
    document_id: int,
    previous_version: str,
    new_version: str,
    file_path: str,
    file_hash: str,
    approver: str,
    locked: bool = True
) -> bool:
    """
    Write detailed audit entry for Controlled transition (ISO 7.5.3 compliance).

    This creates a comprehensive audit record confirming the file has been:
    - Successfully locked under its system-generated ID
    - Renamed to controlled format
    - Hash integrity verified
    - Permissions set to read-only

    Args:
        doc_id: System-generated document ID
        document_id: Database ID
        previous_version: Version before approval
        new_version: Version after approval
        file_path: Final path in controlled folder
        file_hash: SHA-256 hash of the file
        approver: Name of approver
        locked: Whether file was locked successfully

    Returns:
        True if audit log written successfully
    """
    timestamp = datetime.now().isoformat()

    audit_entry = f"""
================================================================================
CONTROLLED DOCUMENT TRANSITION - ISO 22001:2018 Clause 7.5.3
================================================================================
Timestamp:        {timestamp}
Document ID:      {doc_id}
Database ID:      {document_id}
Previous Version: {previous_version}
New Version:      {new_version}
Approved By:      {approver}
--------------------------------------------------------------------------------
FILE OPERATIONS:
  Final Path:     {file_path}
  File Hash:      {file_hash}
  Read-Only Lock: {"YES - File permissions set to read-only" if locked else "NO - Lock failed"}
--------------------------------------------------------------------------------
STATUS: Document successfully indexed under system-generated ID.
        File has been {"LOCKED" if locked else "NOT LOCKED"} per ISO 7.5.3 requirements.
================================================================================

"""

    try:
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(audit_entry)
        return True
    except Exception as e:
        print(f"Warning: Failed to write audit log: {e}")
        return False


# ============================================================================
# API Operations
# ============================================================================

async def get_document(document_id: int) -> dict:
    """
    Fetch document from API.

    Args:
        document_id: Database ID of document

    Returns:
        Document data dictionary
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/documents/{document_id}")
        if response.status_code == 404:
            raise ValueError(f"Document with ID {document_id} not found")
        response.raise_for_status()
        return response.json()


async def update_document(document_id: int, data: dict) -> dict:
    """
    Update document via API.

    Args:
        document_id: Database ID of document
        data: Update data

    Returns:
        Updated document data
    """
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{API_BASE_URL}/documents/{document_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()


async def get_controlled_documents() -> list:
    """
    Get all documents with Controlled status (Master Document Register).

    Returns:
        List of controlled documents
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/documents",
            params={"status": "Controlled"}
        )
        response.raise_for_status()
        return response.json()["documents"]


async def mark_obsolete(document_id: int) -> dict:
    """
    Mark document as Obsolete.

    Args:
        document_id: Database ID of document

    Returns:
        Updated document data
    """
    return await update_document(document_id, {"status": "Obsolete"})


# ============================================================================
# Validation
# ============================================================================

def validate_doc_id_pattern(doc_id: str, department: str) -> tuple[bool, str]:
    """
    Validate doc_id matches the expected pattern for the department.

    Expected format: {DEPT_CODE}-{DOC_TYPE}-{XXX}
    Example: MILL-SOP-001, QAL-REC-002

    Args:
        doc_id: Document ID to validate
        department: Department name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not doc_id:
        return False, "doc_id is required"

    # Get expected department code
    expected_dept_code = DEPARTMENT_CODES.get(department)
    if not expected_dept_code:
        return False, f"Unknown department: {department}"

    # Parse doc_id
    pattern = r'^([A-Z]+)-([A-Z]+)-(\d{3})$'
    match = re.match(pattern, doc_id)

    if not match:
        return False, f"Invalid doc_id format: {doc_id}. Expected {expected_dept_code}-TYPE-XXX"

    actual_dept_code = match.group(1)
    doc_type_code = match.group(2)
    sequence = match.group(3)

    # Validate department code matches
    if actual_dept_code != expected_dept_code:
        return False, f"doc_id department mismatch: {actual_dept_code} != {expected_dept_code} (for {department})"

    # Validate doc_type is valid
    if doc_type_code not in DOC_TYPE_CODES.values():
        return False, f"Invalid document type code in doc_id: {doc_type_code}"

    return True, ""


def validate_mandatory_metadata(document: dict) -> tuple[bool, list]:
    """
    Validate all mandatory metadata fields from Golden Template are present.

    Required fields (ISO 7.5.2):
    - prepared_by
    - approved_by
    - department
    - record_keeper (recommended)

    Args:
        document: Document data from API

    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    missing = []

    # Mandatory fields for Controlled status
    mandatory_fields = [
        ("prepared_by", "Prepared By - ISO 7.5.2 requirement"),
        ("approved_by", "Approved By - ISO 7.5.2 requirement"),
        ("department", "Department - organization requirement"),
    ]

    for field_name, description in mandatory_fields:
        value = document.get(field_name, "").strip()
        if not value:
            missing.append(f"Missing '{field_name}': {description}")

    # Recommended fields (warning only)
    if not document.get("record_keeper", "").strip():
        missing.append("Warning: 'record_keeper' not specified (recommended for ISO compliance)")

    return len([m for m in missing if not m.startswith("Warning")]) == 0, missing


def validate_approval_prerequisites(document: dict) -> tuple[bool, list]:
    """
    Validate all prerequisites for document approval (Controlled transition).

    Checks:
    1. doc_id matches department pattern (e.g., MILL-SOP-001 for Milling)
    2. Mandatory metadata fields are present (prepared_by, approved_by)
    3. Document is not already Obsolete
    4. Version format is valid

    Args:
        document: Document data from API

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    doc_id = document.get("doc_id", "")
    department = document.get("department", "")

    # Check 1: Validate doc_id matches department pattern
    doc_id_valid, doc_id_error = validate_doc_id_pattern(doc_id, department)
    if not doc_id_valid:
        errors.append(f"BLOCKING: {doc_id_error}")

    # Check 2: Validate mandatory metadata from Golden Template
    metadata_valid, metadata_errors = validate_mandatory_metadata(document)
    if not metadata_valid:
        for err in metadata_errors:
            if err.startswith("Warning"):
                errors.append(err)  # Include but don't block
            else:
                errors.append(f"BLOCKING: {err}")

    # Check 3: Document should not be Obsolete
    status = document.get("status", "")
    if status == "Obsolete":
        errors.append("BLOCKING: Cannot approve Obsolete document - create new version instead")

    # Check 4: Version format
    version = document.get("version", "")
    if version:
        try:
            VersionInfo.parse(version)
        except ValueError as e:
            errors.append(f"BLOCKING: {str(e)}")

    # Determine if we have any blocking errors
    blocking_errors = [e for e in errors if e.startswith("BLOCKING")]
    is_valid = len(blocking_errors) == 0

    return is_valid, errors


def validate_version_transition(current_version: str, new_version: str, is_major: bool) -> tuple[bool, str]:
    """
    Validate version transition is correct.

    Args:
        current_version: Current version string
        new_version: Proposed new version string
        is_major: Whether this is a major change

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        current = VersionInfo.parse(current_version)
        new = VersionInfo.parse(new_version)

        if is_major:
            expected = current.increment_major()
        else:
            expected = current.increment_minor()

        if str(new) != str(expected):
            return False, f"Expected version {expected}, got {new_version}"

        return True, ""
    except ValueError as e:
        return False, str(e)


# ============================================================================
# Main Approval Workflow (Controlled Transition)
# ============================================================================

async def approve_document(
    document_id: int,
    is_major_change: bool = False,
    approver_name: str = None
) -> ApprovalResult:
    """
    Main approval workflow for document transition to Controlled status.

    Implements ISO 22001:2018 Clause 7.5.3 (Control of Documented Information):
    1. PREREQUISITE CHECK - Validate doc_id pattern and mandatory metadata
    2. SYSTEM-DRIVEN RENAMING - {doc_id}_v{version}_{title_slug}.pdf
    3. READ-ONLY LOCK - Set file permissions to prevent editing
    4. HASH INTEGRITY SYNC - Compute SHA-256 and update database
    5. AUDIT TRAIL - Log to audit_log.txt

    Args:
        document_id: Database ID of document to approve
        is_major_change: Whether this is a major version change
        approver_name: Name of person approving (optional, uses approved_by if not provided)

    Returns:
        ApprovalResult with status and details
    """
    approval_timestamp = datetime.utcnow().isoformat()

    try:
        # ================================================================
        # STEP 1: Fetch document from database
        # ================================================================
        document = await get_document(document_id)
        doc_id = document.get("doc_id", "")
        current_version = document.get("version", "v0.1")

        # ================================================================
        # STEP 2: PREREQUISITE CHECK
        # Validate doc_id matches department pattern and mandatory metadata
        # ================================================================
        is_valid, errors = validate_approval_prerequisites(document)
        if not is_valid:
            blocking_errors = [e for e in errors if e.startswith("BLOCKING")]
            return ApprovalResult(
                success=False,
                document_id=document_id,
                doc_id=doc_id,
                version=current_version,
                file_path="",
                file_hash="",
                message="Approval blocked: Prerequisites not met",
                errors=errors,
                previous_version=current_version,
                approval_timestamp=approval_timestamp
            )

        # ================================================================
        # STEP 3: Determine new version
        # ================================================================
        current_info = VersionInfo.parse(current_version)

        if current_info.major == 0:
            # First approval: v0.x → v1.0
            new_version = str(current_info.to_first_controlled())
        elif is_major_change:
            new_version = str(current_info.increment_major())
        else:
            new_version = str(current_info.increment_minor())

        # ================================================================
        # STEP 4: Locate source file
        # ================================================================
        source_path = document.get("file_path", "")
        if not source_path or not Path(source_path).exists():
            # Try to find in raw folder
            raw_folder = Path(FOLDERS["raw"])
            possible_files = list(raw_folder.glob("*"))
            if not possible_files:
                return ApprovalResult(
                    success=False,
                    document_id=document_id,
                    doc_id=doc_id,
                    version=current_version,
                    file_path="",
                    file_hash="",
                    message="Source file not found",
                    errors=["No source file available - upload a file first"],
                    previous_version=current_version,
                    approval_timestamp=approval_timestamp
                )
            source_path = str(possible_files[0])

        # ================================================================
        # STEP 5: SYSTEM-DRIVEN RENAMING
        # Generate controlled document with standardized filename:
        # {doc_id}_v{version}_{title_slug}.pdf
        # ================================================================
        title = document.get("title", "Untitled")
        ensure_folders_exist()

        # Update document metadata for cover page generation
        document_for_cover = document.copy()
        document_for_cover["version"] = new_version
        document_for_cover["status"] = "Controlled"
        document_for_cover["approval_date"] = approval_timestamp

        # Generate controlled filename
        source_ext = Path(source_path).suffix
        controlled_filename = generate_controlled_filename(doc_id, new_version, title, source_ext)
        new_file_path = str(Path(FOLDERS["controlled"]) / controlled_filename)

        # Try to generate standardized document with cover page
        try:
            from document_generator import generate_controlled_document
            new_file_path = generate_controlled_document(
                source_pdf=source_path,
                document=document_for_cover,
                output_folder=FOLDERS["controlled"]
            )
        except ImportError:
            # Fallback to simple copy with rename if document_generator not available
            shutil.copy2(source_path, new_file_path)
        except Exception as e:
            # Fallback to simple copy with rename if generation fails
            shutil.copy2(source_path, new_file_path)

        # ================================================================
        # STEP 6: HASH INTEGRITY SYNC
        # Re-compute SHA-256 hash of the renamed/generated file
        # ================================================================
        file_hash = compute_file_hash(new_file_path)

        # ================================================================
        # STEP 7: READ-ONLY LOCK
        # Set file permissions to read-only (ISO 7.5.3 requirement)
        # ================================================================
        locked = False
        try:
            set_readonly(new_file_path)
            locked = True
        except Exception as e:
            # Log warning but don't fail - Windows may have permission issues
            print(f"Warning: Could not set read-only: {e}")

        # ================================================================
        # STEP 8: Archive old version if exists
        # ================================================================
        if document.get("status") == "Controlled" and document.get("file_path"):
            old_path = document.get("file_path")
            if Path(old_path).exists():
                archive_old_version(old_path, doc_id, current_version)

        # ================================================================
        # STEP 9: Update database with final hash and new file_path
        # ================================================================
        approver = approver_name or document.get("approved_by", "System")
        update_data = {
            "status": "Controlled",
            "version": new_version,
            "approval_date": approval_timestamp,
            "file_path": new_file_path,
            "file_hash": file_hash
        }

        await update_document(document_id, update_data)

        # ================================================================
        # STEP 10: AUDIT TRAIL
        # Write comprehensive audit entry confirming controlled transition
        # ================================================================
        audit_logged = log_controlled_transition(
            doc_id=doc_id,
            document_id=document_id,
            previous_version=current_version,
            new_version=new_version,
            file_path=new_file_path,
            file_hash=file_hash,
            approver=approver,
            locked=locked
        )

        return ApprovalResult(
            success=True,
            document_id=document_id,
            doc_id=doc_id,
            version=new_version,
            file_path=new_file_path,
            file_hash=file_hash,
            message=f"Document approved and locked as {new_version}",
            errors=[],
            previous_version=current_version,
            approval_timestamp=approval_timestamp,
            locked=locked,
            audit_logged=audit_logged
        )

    except Exception as e:
        return ApprovalResult(
            success=False,
            document_id=document_id,
            doc_id="",
            version="",
            file_path="",
            file_hash="",
            message=f"Approval failed: {str(e)}",
            errors=[str(e)],
            previous_version="",
            approval_timestamp=approval_timestamp
        )


# ============================================================================
# Master Document Register
# ============================================================================

async def check_master_register() -> dict:
    """
    Check Master Document Register for integrity.

    Returns:
        Dict with status and any issues found
    """
    documents = await get_controlled_documents()

    # Group by doc_id
    by_doc_id = {}
    for doc in documents:
        doc_id = doc.get("doc_id")
        if doc_id not in by_doc_id:
            by_doc_id[doc_id] = []
        by_doc_id[doc_id].append(doc)

    # Check for duplicates
    issues = []
    for doc_id, docs in by_doc_id.items():
        if len(docs) > 1:
            issues.append({
                "doc_id": doc_id,
                "issue": "Multiple controlled versions",
                "versions": [d.get("version") for d in docs],
                "action": "Keep newest, mark others Obsolete"
            })

    return {
        "total_controlled": len(documents),
        "unique_documents": len(by_doc_id),
        "issues": issues,
        "status": "OK" if not issues else "ISSUES_FOUND"
    }


async def fix_duplicate_controlled(doc_id: str) -> dict:
    """
    Fix duplicate controlled documents by keeping only newest.

    Args:
        doc_id: Document ID with duplicates

    Returns:
        Result of fix operation
    """
    documents = await get_controlled_documents()

    # Filter to this doc_id
    matching = [d for d in documents if d.get("doc_id") == doc_id]

    if len(matching) <= 1:
        return {"status": "OK", "message": "No duplicates found"}

    # Sort by version (descending) to keep newest
    matching.sort(key=lambda d: VersionInfo.parse(d.get("version", "v0.0")).major * 100 +
                                VersionInfo.parse(d.get("version", "v0.0")).minor,
                  reverse=True)

    # Keep first (newest), mark rest as Obsolete
    kept = matching[0]
    obsoleted = []

    for doc in matching[1:]:
        await mark_obsolete(doc["id"])
        obsoleted.append(doc["version"])
        log_audit(
            action="MARKED_OBSOLETE",
            doc_id=doc_id,
            user="System",
            details=f"Duplicate cleanup: {doc['version']} obsoleted, keeping {kept['version']}"
        )

    return {
        "status": "FIXED",
        "kept_version": kept["version"],
        "obsoleted_versions": obsoleted
    }


# ============================================================================
# Utility Functions
# ============================================================================

def verify_file_integrity(file_path: str, expected_hash: str) -> bool:
    """
    Verify file has not been tampered with.

    Args:
        file_path: Path to file
        expected_hash: Expected SHA-256 hash

    Returns:
        True if hash matches, False otherwise
    """
    if not Path(file_path).exists():
        return False

    actual_hash = compute_file_hash(file_path)
    return actual_hash == expected_hash


def list_raw_documents() -> list:
    """
    List all documents in raw folder.

    Returns:
        List of file paths
    """
    raw_folder = Path(FOLDERS["raw"])
    if not raw_folder.exists():
        return []

    supported_ext = [".pdf", ".docx", ".doc", ".txt"]
    files = []
    for ext in supported_ext:
        files.extend(raw_folder.glob(f"*{ext}"))

    return [str(f) for f in sorted(files)]


def list_controlled_documents() -> list:
    """
    List all documents in controlled folder.

    Returns:
        List of file paths
    """
    controlled_folder = Path(FOLDERS["controlled"])
    if not controlled_folder.exists():
        return []

    return [str(f) for f in sorted(controlled_folder.iterdir()) if f.is_file()]


def list_archived_documents() -> list:
    """
    List all documents in archive folder.

    Returns:
        List of file paths
    """
    archive_folder = Path(FOLDERS["archive"])
    if not archive_folder.exists():
        return []

    return [str(f) for f in sorted(archive_folder.iterdir()) if f.is_file()]
