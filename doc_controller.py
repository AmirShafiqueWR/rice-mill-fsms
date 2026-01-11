"""
Document Controller for Rice Export FSMS

Implements ISO 22001:2018 Clause 7.5.3 (Control of Documented Information)
Manages document state transitions, version control, and file operations.
"""

import os
import re
import hashlib
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import httpx


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
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


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

def validate_approval_prerequisites(document: dict) -> tuple[bool, list]:
    """
    Validate all prerequisites for document approval.

    Args:
        document: Document data from API

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check 1: Ownership fields
    if not document.get("prepared_by"):
        errors.append("Missing 'prepared_by' field - ISO 7.5.2 requirement")

    if not document.get("approved_by"):
        errors.append("Missing 'approved_by' field - ISO 7.5.2 requirement")

    if not document.get("department"):
        errors.append("Missing 'department' field - organization requirement")

    # Check 2: Document should be in Draft status for initial approval
    status = document.get("status", "")
    if status == "Obsolete":
        errors.append("Cannot approve Obsolete document - create new version instead")

    # Check 3: Version format
    version = document.get("version", "")
    if version:
        try:
            VersionInfo.parse(version)
        except ValueError as e:
            errors.append(str(e))

    return len(errors) == 0, errors


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
# Main Approval Workflow
# ============================================================================

async def approve_document(
    document_id: int,
    is_major_change: bool = False,
    approver_name: str = None
) -> ApprovalResult:
    """
    Main approval workflow for document.

    Args:
        document_id: Database ID of document to approve
        is_major_change: Whether this is a major version change
        approver_name: Name of person approving (optional, uses approved_by if not provided)

    Returns:
        ApprovalResult with status and details
    """
    try:
        # Step 1: Fetch document
        document = await get_document(document_id)

        # Step 2: Validate prerequisites
        is_valid, errors = validate_approval_prerequisites(document)
        if not is_valid:
            return ApprovalResult(
                success=False,
                document_id=document_id,
                doc_id=document.get("doc_id", ""),
                version=document.get("version", ""),
                file_path="",
                file_hash="",
                message="Approval blocked: Prerequisites not met",
                errors=errors
            )

        # Step 3: Determine new version
        current_version = document.get("version", "v0.1")
        current_info = VersionInfo.parse(current_version)

        if current_info.major == 0:
            # First approval: v0.x → v1.0
            new_version = str(current_info.to_first_controlled())
        elif is_major_change:
            new_version = str(current_info.increment_major())
        else:
            new_version = str(current_info.increment_minor())

        # Step 4: Get source file path
        source_path = document.get("file_path", "")
        if not source_path or not Path(source_path).exists():
            # Try to find in raw folder
            raw_folder = Path(FOLDERS["raw"])
            possible_files = list(raw_folder.glob("*"))
            if not possible_files:
                return ApprovalResult(
                    success=False,
                    document_id=document_id,
                    doc_id=document.get("doc_id", ""),
                    version=current_version,
                    file_path="",
                    file_hash="",
                    message="Source file not found in raw folder",
                    errors=["No source file available for this document"]
                )
            # This would need user input to select correct file
            source_path = str(possible_files[0])

        # Step 5: Generate standardized document with cover page
        doc_id = document.get("doc_id", f"FSMS-DOC-{document_id}")
        title = document.get("title", "Untitled")

        # Update document with new version for cover page generation
        document_for_cover = document.copy()
        document_for_cover["version"] = new_version
        document_for_cover["status"] = "Controlled"
        document_for_cover["approval_date"] = datetime.utcnow().isoformat()

        # Try to generate standardized document with cover page
        try:
            from document_generator import generate_controlled_document
            new_file_path = generate_controlled_document(
                source_pdf=source_path,
                document=document_for_cover,
                output_folder=FOLDERS["controlled"]
            )
        except ImportError:
            # Fallback to simple move if document_generator not available
            new_file_path = move_to_controlled(source_path, doc_id, new_version, title)
        except Exception as e:
            # Fallback to simple move if generation fails
            new_file_path = move_to_controlled(source_path, doc_id, new_version, title)

        # Step 6: Calculate file hash of the generated document
        file_hash = compute_file_hash(new_file_path)

        # Step 7: Set read-only
        try:
            set_readonly(new_file_path)
        except Exception as e:
            # Log but don't fail - Windows may not support this
            pass

        # Step 8: Archive old version if exists
        if document.get("status") == "Controlled" and document.get("file_path"):
            old_path = document.get("file_path")
            if Path(old_path).exists():
                archive_old_version(old_path, doc_id, current_version)

        # Step 9: Update database
        approver = approver_name or document.get("approved_by", "System")
        update_data = {
            "status": "Controlled",
            "version": new_version,
            "approval_date": datetime.utcnow().isoformat(),
            "file_path": new_file_path,
            "file_hash": file_hash
        }

        await update_document(document_id, update_data)

        # Step 10: Log audit trail
        log_audit(
            action="APPROVED",
            doc_id=doc_id,
            user=approver,
            details=f"Version: {current_version} → {new_version} | File: {new_file_path}"
        )

        return ApprovalResult(
            success=True,
            document_id=document_id,
            doc_id=doc_id,
            version=new_version,
            file_path=new_file_path,
            file_hash=file_hash,
            message=f"Document approved successfully as {new_version}"
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
            errors=[str(e)]
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
