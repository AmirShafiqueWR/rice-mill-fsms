"""
Unit Tests for SQLModel Models

Tests validation rules, relationships, and model behavior
for Document and Task models.
"""

import pytest
from sqlmodel import Session

from models import Document, Task, VALID_DEPARTMENTS, STATUS_TRANSITIONS


# ============================================================================
# Document Model Tests
# ============================================================================

class TestDocumentModel:
    """Tests for Document SQLModel."""

    def test_document_requires_ownership_fields(self, test_db: Session):
        """Document must have prepared_by, approved_by, record_keeper."""
        # Valid document with all required fields
        doc = Document(
            doc_id="FSMS-TEST-001",
            title="Test",
            department="Quality",
            version="v1.0",
            prepared_by="Preparer",
            approved_by="Approver",
            record_keeper="Keeper",
        )
        test_db.add(doc)
        test_db.commit()

        assert doc.id is not None
        assert doc.prepared_by == "Preparer"
        assert doc.approved_by == "Approver"
        assert doc.record_keeper == "Keeper"

    def test_version_format_validation(self, test_db: Session):
        """Version must match v\\d+\\.\\d+ pattern."""
        doc = Document(
            doc_id="FSMS-VER-001",
            title="Version Test",
            department="Quality",
            version="v1.0",
            prepared_by="Test",
            approved_by="Test",
            record_keeper="Test",
        )

        # Valid versions
        assert doc.validate_version_format() is True

        doc.version = "v2.1"
        assert doc.validate_version_format() is True

        doc.version = "v10.99"
        assert doc.validate_version_format() is True

        # Invalid versions
        doc.version = "1.0"
        assert doc.validate_version_format() is False

        doc.version = "v1"
        assert doc.validate_version_format() is False

        doc.version = "version1.0"
        assert doc.validate_version_format() is False

        doc.version = "v1.0.0"
        assert doc.validate_version_format() is False

    def test_status_enum_validation(self, test_db: Session, sample_document: Document):
        """Status must be Draft, Controlled, or Obsolete."""
        assert sample_document.status == "Draft"

        # Valid status values
        sample_document.status = "Controlled"
        test_db.commit()
        assert sample_document.status == "Controlled"

        sample_document.status = "Obsolete"
        test_db.commit()
        assert sample_document.status == "Obsolete"

    def test_department_enum_validation(self, test_db: Session):
        """Department must be from approved list."""
        doc = Document(
            doc_id="FSMS-DEPT-001",
            title="Dept Test",
            department="Quality",
            version="v1.0",
            prepared_by="Test",
            approved_by="Test",
            record_keeper="Test",
        )

        # Test all valid departments
        for dept in VALID_DEPARTMENTS:
            doc.department = dept
            assert doc.validate_department() is True

        # Invalid department
        doc.department = "InvalidDept"
        assert doc.validate_department() is False

    def test_status_transitions(self, test_db: Session, sample_document: Document):
        """Status can only transition forward: Draft → Controlled → Obsolete."""
        # Initial status is Draft
        assert sample_document.status == "Draft"

        # Draft can go to Controlled
        assert sample_document.can_transition_to("Controlled") is True
        assert sample_document.can_transition_to("Obsolete") is False
        assert sample_document.can_transition_to("Draft") is False

        # Update to Controlled
        sample_document.status = "Controlled"
        test_db.commit()

        # Controlled can go to Obsolete
        assert sample_document.can_transition_to("Obsolete") is True
        assert sample_document.can_transition_to("Draft") is False
        assert sample_document.can_transition_to("Controlled") is False

        # Update to Obsolete
        sample_document.status = "Obsolete"
        test_db.commit()

        # Obsolete cannot transition anywhere
        assert sample_document.can_transition_to("Draft") is False
        assert sample_document.can_transition_to("Controlled") is False
        assert sample_document.can_transition_to("Obsolete") is False

    def test_version_hash_computed(self, test_db: Session, sample_document: Document):
        """Version hash should be computed for tamper detection."""
        assert sample_document.version_hash is not None
        assert len(sample_document.version_hash) == 64  # SHA-256 hex length

        # Hash should change when document changes
        original_hash = sample_document.version_hash
        sample_document.title = "Modified Title"
        sample_document.update_version_hash()
        assert sample_document.version_hash != original_hash

    def test_iso_clauses_json_handling(self, test_db: Session, sample_document: Document):
        """ISO clauses should be stored as JSON and retrieved as list."""
        clauses = ["7.1", "7.2", "8.5.1"]
        sample_document.set_iso_clauses(clauses)
        test_db.commit()

        retrieved = sample_document.get_iso_clauses()
        assert retrieved == clauses

    def test_document_unique_doc_id(self, test_db: Session, sample_document: Document):
        """doc_id must be unique."""
        duplicate = Document(
            doc_id=sample_document.doc_id,  # Same doc_id
            title="Duplicate",
            department="Quality",
            version="v1.0",
            prepared_by="Test",
            approved_by="Test",
            record_keeper="Test",
        )

        test_db.add(duplicate)
        with pytest.raises(Exception):  # IntegrityError
            test_db.commit()


# ============================================================================
# Task Model Tests
# ============================================================================

class TestTaskModel:
    """Tests for Task SQLModel."""

    def test_task_requires_iso_clause(self, test_db: Session, sample_document: Document):
        """Task must have non-empty iso_clause."""
        task = Task(
            document_id=sample_document.id,
            task_description="Test task",
            iso_clause="8.5.1",
            assigned_department="Quality",
        )

        assert task.validate_iso_clause() is True

        # Empty string should fail
        task.iso_clause = ""
        assert task.validate_iso_clause() is False

        # Whitespace only should fail
        task.iso_clause = "   "
        assert task.validate_iso_clause() is False

    def test_task_priority_values(self, test_db: Session, sample_document: Document):
        """Task priority must be Critical, High, Medium, or Low."""
        valid_priorities = ["Critical", "High", "Medium", "Low"]

        for priority in valid_priorities:
            task = Task(
                document_id=sample_document.id,
                task_description=f"Priority {priority} task",
                iso_clause="8.5.1",
                assigned_department="Quality",
                priority=priority,
            )
            test_db.add(task)
            test_db.commit()
            assert task.priority == priority
            test_db.delete(task)
            test_db.commit()

    def test_task_status_values(self, test_db: Session, sample_document: Document):
        """Task status must be Pending, Completed, or Overdue."""
        valid_statuses = ["Pending", "Completed", "Overdue"]

        for status in valid_statuses:
            task = Task(
                document_id=sample_document.id,
                task_description=f"Status {status} task",
                iso_clause="8.5.1",
                assigned_department="Quality",
                status=status,
            )
            test_db.add(task)
            test_db.commit()
            assert task.status == status
            test_db.delete(task)
            test_db.commit()

    def test_task_default_values(self, test_db: Session, sample_document: Document):
        """Task should have correct default values."""
        task = Task(
            document_id=sample_document.id,
            task_description="Minimal task",
            iso_clause="8.5.1",
            assigned_department="Quality",
        )
        test_db.add(task)
        test_db.commit()

        assert task.priority == "Medium"
        assert task.status == "Pending"
        assert task.created_at is not None


# ============================================================================
# Relationship Tests
# ============================================================================

class TestRelationships:
    """Tests for Document-Task relationships."""

    def test_document_task_relationship(self, test_db: Session, sample_document: Document):
        """One document should have many tasks."""
        # Create multiple tasks for the document
        for i in range(3):
            task = Task(
                document_id=sample_document.id,
                task_description=f"Task {i}",
                iso_clause="8.5.1",
                assigned_department="Quality",
            )
            test_db.add(task)
        test_db.commit()

        # Refresh to load relationships
        test_db.refresh(sample_document)

        assert len(sample_document.tasks) == 3

    def test_cascade_delete(self, test_db: Session):
        """Deleting document should delete all its tasks."""
        # Create document
        doc = Document(
            doc_id="FSMS-CASCADE-001",
            title="Cascade Test",
            department="Quality",
            version="v1.0",
            prepared_by="Test",
            approved_by="Test",
            record_keeper="Test",
        )
        test_db.add(doc)
        test_db.commit()

        doc_id = doc.id

        # Create tasks
        for i in range(3):
            task = Task(
                document_id=doc_id,
                task_description=f"Task {i}",
                iso_clause="8.5.1",
                assigned_department="Quality",
            )
            test_db.add(task)
        test_db.commit()

        # Verify tasks exist
        from sqlmodel import select
        tasks_before = test_db.exec(select(Task).where(Task.document_id == doc_id)).all()
        assert len(tasks_before) == 3

        # Delete document
        test_db.delete(doc)
        test_db.commit()

        # Verify tasks are deleted
        tasks_after = test_db.exec(select(Task).where(Task.document_id == doc_id)).all()
        assert len(tasks_after) == 0

    def test_task_references_document(self, test_db: Session, sample_task: Task):
        """Task should reference its parent document."""
        test_db.refresh(sample_task)
        assert sample_task.document is not None
        assert sample_task.document.id == sample_task.document_id
