"""
End-to-End Workflow Tests for Rice Export FSMS

Tests complete workflows and business logic scenarios
to ensure the system works correctly as a whole.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Document, Task


# ============================================================================
# Document Lifecycle Tests
# ============================================================================

class TestDocumentLifecycle:
    """End-to-end tests for document lifecycle."""

    def test_full_document_lifecycle(self, test_client: TestClient, test_db: Session):
        """
        Test complete document lifecycle:
        Create Draft → Update to Controlled → Add Tasks → Verify
        """
        # Step 1: Create document in Draft status
        doc_data = {
            "doc_id": "FSMS-LIFECYCLE-001",
            "title": "Lifecycle Test Document",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "QA Manager",
            "approved_by": "Plant Director",
            "record_keeper": "Document Control",
        }
        create_response = test_client.post("/documents", json=doc_data)
        assert create_response.status_code == 201
        doc = create_response.json()
        doc_id = doc["id"]
        assert doc["status"] == "Draft"

        # Step 2: Update to Controlled status
        update_response = test_client.patch(
            f"/documents/{doc_id}",
            json={"status": "Controlled"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "Controlled"

        # Step 3: Add tasks to controlled document
        tasks_data = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Verify moisture content before milling",
                    "action": "verify",
                    "object": "moisture content",
                    "iso_clause": "8.5.1",
                    "critical_limit": "14% max",
                    "frequency": "Per batch",
                    "assigned_department": "Quality",
                    "priority": "Critical",
                },
                {
                    "document_id": doc_id,
                    "task_description": "Record temperature readings",
                    "action": "record",
                    "object": "temperature",
                    "iso_clause": "7.2",
                    "frequency": "Every 4 hours",
                    "assigned_department": "Milling",
                    "priority": "High",
                },
            ]
        }
        tasks_response = test_client.post("/tasks", json=tasks_data)
        assert tasks_response.status_code == 201
        assert tasks_response.json()["created_count"] == 2

        # Step 4: Verify document with tasks
        doc_with_tasks = test_client.get(f"/documents/{doc_id}/tasks")
        assert doc_with_tasks.status_code == 200
        data = doc_with_tasks.json()
        assert data["document"]["status"] == "Controlled"
        assert len(data["tasks"]) == 2

    def test_document_deletion_cascades_to_tasks(self, test_client: TestClient, test_db: Session):
        """
        Test that soft-deleting a document marks it Obsolete.
        Note: Actual CASCADE delete would remove tasks, but soft delete preserves them.
        """
        # Create document
        doc_data = {
            "doc_id": "FSMS-CASCADE-TEST",
            "title": "Cascade Test",
            "department": "Milling",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Add tasks
        tasks_data = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Task to be orphaned",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                }
            ]
        }
        test_client.post("/tasks", json=tasks_data)

        # Soft delete document
        delete_response = test_client.delete(f"/documents/{doc_id}")
        assert delete_response.status_code == 204

        # Verify document is Obsolete (not actually deleted)
        get_response = test_client.get(f"/documents/{doc_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "Obsolete"

        # Tasks should still exist and be accessible
        tasks_response = test_client.get(f"/documents/{doc_id}/tasks")
        assert tasks_response.status_code == 200
        assert len(tasks_response.json()["tasks"]) == 1

    def test_duplicate_prevention(self, test_client: TestClient):
        """Cannot create documents with same doc_id."""
        doc_data = {
            "doc_id": "FSMS-UNIQUE-001",
            "title": "First Document",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }

        # Create first document
        first_response = test_client.post("/documents", json=doc_data)
        assert first_response.status_code == 201

        # Try to create duplicate
        doc_data["title"] = "Duplicate Document"
        second_response = test_client.post("/documents", json=doc_data)
        assert second_response.status_code == 400
        assert second_response.json()["error_code"] == "DUPLICATE_DOC_ID"

    def test_version_progression(self, test_client: TestClient):
        """Test version updates: v1.0 → v1.1 → v2.0."""
        doc_data = {
            "doc_id": "FSMS-VERSION-001",
            "title": "Version Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }

        # Create with v1.0
        create_response = test_client.post("/documents", json=doc_data)
        assert create_response.status_code == 201
        doc_id = create_response.json()["id"]
        assert create_response.json()["version"] == "v1.0"

        # Update to v1.1
        update_response = test_client.patch(
            f"/documents/{doc_id}",
            json={"version": "v1.1"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == "v1.1"

        # Update to v2.0
        update_response = test_client.patch(
            f"/documents/{doc_id}",
            json={"version": "v2.0"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == "v2.0"

        # Invalid version should fail
        invalid_response = test_client.patch(
            f"/documents/{doc_id}",
            json={"version": "2.0"}  # Missing 'v' prefix
        )
        assert invalid_response.status_code == 422


# ============================================================================
# ISO Compliance Workflow Tests
# ============================================================================

class TestISOComplianceWorkflow:
    """Tests for ISO 22001:2018 compliance requirements."""

    def test_iso_compliance_workflow(self, test_client: TestClient):
        """
        Document requires ownership fields throughout lifecycle.
        Tests that all ISO-required fields are enforced.
        """
        # All ownership fields present - should succeed
        complete_doc = {
            "doc_id": "FSMS-ISO-001",
            "title": "ISO Compliant Document",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Quality Manager",
            "approved_by": "Plant Director",
            "record_keeper": "Document Control",
            "review_cycle_months": 12,
            "iso_clauses": ["7.1", "7.2", "8.5.1"],
        }
        response = test_client.post("/documents", json=complete_doc)
        assert response.status_code == 201

        # Verify ISO clauses stored
        doc_id = response.json()["id"]
        get_response = test_client.get(f"/documents/{doc_id}")
        assert get_response.json()["iso_clauses"] is not None

    def test_task_requires_iso_clause_workflow(self, test_client: TestClient):
        """
        Every task must reference an ISO clause for compliance.
        """
        # Create document first
        doc_data = {
            "doc_id": "FSMS-ISO-TASK-001",
            "title": "Task ISO Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Task with ISO clause - should succeed
        valid_task = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Compliant task",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                }
            ]
        }
        valid_response = test_client.post("/tasks", json=valid_task)
        assert valid_response.status_code == 201

        # Task without ISO clause - should fail
        invalid_task = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Non-compliant task",
                    # Missing iso_clause
                    "assigned_department": "Quality",
                }
            ]
        }
        invalid_response = test_client.post("/tasks", json=invalid_task)
        assert invalid_response.status_code == 422

    def test_status_transition_compliance(self, test_client: TestClient):
        """
        Status must follow one-way transitions for document control.
        Draft → Controlled → Obsolete (cannot go backwards)
        """
        doc_data = {
            "doc_id": "FSMS-STATUS-001",
            "title": "Status Transition Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Draft → Controlled: Valid
        response1 = test_client.patch(
            f"/documents/{doc_id}",
            json={"status": "Controlled"}
        )
        assert response1.status_code == 200

        # Controlled → Draft: Invalid (backwards)
        response2 = test_client.patch(
            f"/documents/{doc_id}",
            json={"status": "Draft"}
        )
        assert response2.status_code == 400
        assert response2.json()["error_code"] == "INVALID_TRANSITION"

        # Controlled → Obsolete: Valid
        response3 = test_client.patch(
            f"/documents/{doc_id}",
            json={"status": "Obsolete"}
        )
        assert response3.status_code == 200

        # Obsolete → anything: Invalid
        response4 = test_client.patch(
            f"/documents/{doc_id}",
            json={"status": "Controlled"}
        )
        assert response4.status_code == 400


# ============================================================================
# Task Workflow Tests
# ============================================================================

class TestTaskWorkflow:
    """End-to-end tests for task workflows."""

    def test_task_completion_workflow(self, test_client: TestClient):
        """Test task status progression: Pending → Completed."""
        # Create document
        doc_data = {
            "doc_id": "FSMS-TASK-WORKFLOW",
            "title": "Task Workflow Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Create task in Pending status
        task_data = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Complete this task",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                    "priority": "High",
                }
            ]
        }
        task_response = test_client.post("/tasks", json=task_data)
        task_id = task_response.json()["task_ids"][0]

        # Verify initial status
        get_response = test_client.get(f"/tasks/{task_id}")
        assert get_response.json()["status"] == "Pending"

        # Complete the task
        complete_response = test_client.patch(
            f"/tasks/{task_id}",
            json={"status": "Completed"}
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "Completed"

    def test_task_priority_escalation(self, test_client: TestClient):
        """Test priority changes: Medium → High → Critical."""
        # Create document
        doc_data = {
            "doc_id": "FSMS-PRIORITY-TEST",
            "title": "Priority Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Create task with Medium priority (default)
        task_data = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Escalating task",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                }
            ]
        }
        task_response = test_client.post("/tasks", json=task_data)
        task_id = task_response.json()["task_ids"][0]

        # Escalate to High
        high_response = test_client.patch(
            f"/tasks/{task_id}",
            json={"priority": "High"}
        )
        assert high_response.json()["priority"] == "High"

        # Escalate to Critical
        critical_response = test_client.patch(
            f"/tasks/{task_id}",
            json={"priority": "Critical"}
        )
        assert critical_response.json()["priority"] == "Critical"

    def test_filter_tasks_by_multiple_criteria(self, test_client: TestClient):
        """Test filtering tasks by department, priority, and status."""
        # Create document
        doc_data = {
            "doc_id": "FSMS-FILTER-TEST",
            "title": "Filter Test",
            "department": "Quality",
            "version": "v1.0",
            "prepared_by": "Test",
            "approved_by": "Test",
            "record_keeper": "Test",
        }
        doc_response = test_client.post("/documents", json=doc_data)
        doc_id = doc_response.json()["id"]

        # Create diverse tasks
        tasks_data = {
            "tasks": [
                {
                    "document_id": doc_id,
                    "task_description": "Quality Critical Pending",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                    "priority": "Critical",
                    "status": "Pending",
                },
                {
                    "document_id": doc_id,
                    "task_description": "Milling High Completed",
                    "iso_clause": "7.2",
                    "assigned_department": "Milling",
                    "priority": "High",
                    "status": "Completed",
                },
            ]
        }
        test_client.post("/tasks", json=tasks_data)

        # Filter by department
        dept_response = test_client.get("/tasks", params={"department": "Quality"})
        quality_tasks = [t for t in dept_response.json() if t["assigned_department"] == "Quality"]
        assert len(quality_tasks) >= 1

        # Filter by priority
        priority_response = test_client.get("/tasks", params={"priority": "Critical"})
        critical_tasks = [t for t in priority_response.json() if t["priority"] == "Critical"]
        assert len(critical_tasks) >= 1

        # Filter by status
        status_response = test_client.get("/tasks", params={"status": "Completed"})
        completed_tasks = [t for t in status_response.json() if t["status"] == "Completed"]
        assert len(completed_tasks) >= 1
