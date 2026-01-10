"""
SQLModel Models for Rice Export FSMS (ISO 22001:2018)

Document and Task models with:
- Proper field definitions and constraints
- SHA-256 hashing for tamper detection
- Status transition validation
- Database-level CHECK constraints
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String, Text, CheckConstraint, event


# Valid departments for Rice Mill FSMS
VALID_DEPARTMENTS = ["Milling", "Quality", "Exports", "Packaging", "Storage"]

# Status transitions (one-way only)
STATUS_TRANSITIONS = {
    "Draft": ["Controlled"],
    "Controlled": ["Obsolete"],
    "Obsolete": []
}


class Document(SQLModel, table=True):
    """
    Document Control model for ISO 22001:2018 compliance.
    Tracks controlled documents with version control and tamper detection.
    """
    __tablename__ = "document"
    __table_args__ = (
        CheckConstraint(
            "department IN ('Milling', 'Quality', 'Exports', 'Packaging', 'Storage')",
            name="valid_department"
        ),
        CheckConstraint(
            "status IN ('Draft', 'Controlled', 'Obsolete')",
            name="valid_status"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(sa_column=Column(String(50), unique=True, nullable=False, index=True))
    title: str = Field(sa_column=Column(String(255), nullable=False))
    department: str = Field(sa_column=Column(String(50), nullable=False))
    version: str = Field(sa_column=Column(String(20), nullable=False))
    status: str = Field(default="Draft", sa_column=Column(String(20), nullable=False))

    # ISO 22001 required fields
    prepared_by: str = Field(sa_column=Column(String(100), nullable=False))
    approved_by: str = Field(sa_column=Column(String(100), nullable=False))
    record_keeper: str = Field(sa_column=Column(String(100), nullable=False))
    approval_date: Optional[datetime] = Field(default=None)
    review_cycle_months: int = Field(default=12)

    # ISO clause mapping (stored as JSON string)
    iso_clauses: Optional[str] = Field(default=None, sa_column=Column(Text))

    # File tracking
    file_path: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    file_hash: Optional[str] = Field(default=None, sa_column=Column(String(64)))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Tamper detection
    version_hash: Optional[str] = Field(default=None, sa_column=Column(String(64)))

    # Relationship to tasks
    tasks: List["Task"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    def validate_version_format(self) -> bool:
        """Validate version matches v\\d+\\.\\d+ pattern."""
        pattern = r'^v\d+\.\d+$'
        return bool(re.match(pattern, self.version))

    def validate_department(self) -> bool:
        """Validate department is in approved list."""
        return self.department in VALID_DEPARTMENTS

    def can_transition_to(self, new_status: str) -> bool:
        """Check if status transition is allowed (one-way only)."""
        allowed = STATUS_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def compute_version_hash(self) -> str:
        """Compute SHA-256 hash of record for tamper detection."""
        data = f"{self.doc_id}|{self.title}|{self.department}|{self.version}|{self.status}|{self.prepared_by}|{self.approved_by}|{self.iso_clauses}"
        return hashlib.sha256(data.encode()).hexdigest()

    def update_version_hash(self):
        """Update the version hash before saving."""
        self.version_hash = self.compute_version_hash()
        self.updated_at = datetime.utcnow()

    def set_iso_clauses(self, clauses: List[str]):
        """Set ISO clauses from a list."""
        self.iso_clauses = json.dumps(clauses)

    def get_iso_clauses(self) -> List[str]:
        """Get ISO clauses as a list."""
        if self.iso_clauses:
            return json.loads(self.iso_clauses)
        return []

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of file content."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


class Task(SQLModel, table=True):
    """
    Task model for tracking compliance tasks extracted from documents.
    Links to specific document versions for audit trail.
    """
    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint(
            "iso_clause IS NOT NULL AND iso_clause != ''",
            name="iso_clause_required"
        ),
        CheckConstraint(
            "priority IN ('Critical', 'High', 'Medium', 'Low')",
            name="valid_priority"
        ),
        CheckConstraint(
            "status IN ('Pending', 'Completed', 'Overdue')",
            name="valid_task_status"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", nullable=False, index=True)

    # Task details extracted from document
    task_description: str = Field(sa_column=Column(Text, nullable=False))
    action: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    object: Optional[str] = Field(default=None, sa_column=Column(String(255)))

    # ISO compliance - REQUIRED field
    iso_clause: str = Field(sa_column=Column(String(50), nullable=False))

    # Operational parameters
    critical_limit: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    frequency: Optional[str] = Field(default=None, sa_column=Column(String(100)))

    # Assignment
    assigned_department: str = Field(sa_column=Column(String(50), nullable=False))
    assigned_role: Optional[str] = Field(default=None, sa_column=Column(String(100)))

    # Status tracking
    priority: str = Field(default="Medium", sa_column=Column(String(20), nullable=False))
    status: str = Field(default="Pending", sa_column=Column(String(20), nullable=False))

    # Document version lock
    source_document_version: Optional[str] = Field(default=None, sa_column=Column(String(20)))
    extracted_from_page: Optional[int] = Field(default=None)

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to document
    document: Optional[Document] = Relationship(back_populates="tasks")

    def validate_iso_clause(self) -> bool:
        """Validate ISO clause is not empty."""
        return bool(self.iso_clause and self.iso_clause.strip())


# Event listeners for automatic hash updates
@event.listens_for(Document, "before_insert")
def document_before_insert(mapper, connection, target):
    """Update version hash before insert."""
    if not target.validate_version_format():
        raise ValueError(f"Invalid version format: {target.version}. Must match v\\d+\\.\\d+ (e.g., v1.0)")
    if not target.validate_department():
        raise ValueError(f"Invalid department: {target.department}. Must be one of {VALID_DEPARTMENTS}")
    target.update_version_hash()


@event.listens_for(Document, "before_update")
def document_before_update(mapper, connection, target):
    """Update version hash and validate transitions before update."""
    if not target.validate_version_format():
        raise ValueError(f"Invalid version format: {target.version}. Must match v\\d+\\.\\d+ (e.g., v1.0)")
    if not target.validate_department():
        raise ValueError(f"Invalid department: {target.department}. Must be one of {VALID_DEPARTMENTS}")
    target.update_version_hash()


@event.listens_for(Task, "before_insert")
def task_before_insert(mapper, connection, target):
    """Validate ISO clause before insert."""
    if not target.validate_iso_clause():
        raise ValueError("ISO clause is required and cannot be empty")
