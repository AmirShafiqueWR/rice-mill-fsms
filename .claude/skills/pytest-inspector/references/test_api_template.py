"""
Integration Tests for FastAPI Endpoints

Tests all CRUD operations for Document and Task endpoints,
including validation, error handling, and filtering.
"""

import pytest
from fastapi.testclient import TestClient

from models import Document, Task


# ============================================================================
# Document Endpoint Tests
# ============================================================================

class TestDocumentEndpoints:
    """Integration tests for /documents endpoints."""

    def test_create_document_success(self, test_client: TestClient, sample_document_data: dict):
        """POST /documents with valid data should return 201."""
        response = test_client.post("/documents", json=sample_document_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["doc_id"] == sample_document_data["doc_id"]
        assert data["title"] == sample_document_data["title"]
        assert data["department"] == sample_document_data["department"]
        assert data["status"] == "Draft"
        assert data["version_hash"] is not None

    def test_create_document_missing_field(self, test_client: TestClient):
        """POST /documents without required field should return 422."""
        incomplete_data = {
            "doc_id": "FSMS-INCOMPLETE",
            "title": "Incomplete Doc",
            # Missing: department, version, prepared_by, approved_by, record_keeper
        }

        response = test_client.post("/documents", json=incomplete_data)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_document_invalid_department(self, test_client: TestClient, sample_document_data: dict):
        """POST /documents with invalid department should return 422."""
        sample_document_data["doc_id"] = "FSMS-INVALID-DEPT"
        sample_document_data["department"] = "InvalidDepartment"

        response = test_client.post("/documents", json=sample_document_data)

        assert response.status_code == 422

    def test_create_document_invalid_version(self, test_client: TestClient, sample_document_data: dict):
        """POST /documents with invalid version format should return 422."""
        sample_document_data["doc_id"] = "FSMS-INVALID-VER"
        sample_document_data["version"] = "1.0"  # Missing 'v' prefix

        response = test_client.post("/documents", json=sample_document_data)

        assert response.status_code == 422

    def test_create_document_duplicate_doc_id(
        self, test_client: TestClient, sample_document: Document, sample_document_data: dict
    ):
        """POST /documents with duplicate doc_id should return 400."""
        # sample_document already exists with this doc_id
        response = test_client.post("/documents", json=sample_document_data)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "DUPLICATE_DOC_ID"

    def test_get_documents(self, test_client: TestClient, multiple_documents: list[Document]):
        """GET /documents should return list of documents."""
        response = test_client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "documents" in data
        assert data["total"] >= 3
        assert len(data["documents"]) >= 3

    def test_get_documents_filter_by_department(
        self, test_client: TestClient, multiple_documents: list[Document]
    ):
        """GET /documents?department=Milling should filter results."""
        response = test_client.get("/documents", params={"department": "Milling"})

        assert response.status_code == 200
        data = response.json()
        for doc in data["documents"]:
            assert doc["department"] == "Milling"

    def test_get_documents_filter_by_status(
        self, test_client: TestClient, multiple_documents: list[Document]
    ):
        """GET /documents?status=Controlled should filter results."""
        response = test_client.get("/documents", params={"status": "Controlled"})

        assert response.status_code == 200
        data = response.json()
        for doc in data["documents"]:
            assert doc["status"] == "Controlled"

    def test_get_documents_pagination(self, test_client: TestClient, multiple_documents: list[Document]):
        """GET /documents with limit and offset should paginate."""
        response = test_client.get("/documents", params={"limit": 2, "offset": 0})

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) <= 2

    def test_get_document_by_id(self, test_client: TestClient, sample_document: Document):
        """GET /documents/{id} should return single document."""
        response = test_client.get(f"/documents/{sample_document.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document.id
        assert data["doc_id"] == sample_document.doc_id

    def test_get_document_not_found(self, test_client: TestClient):
        """GET /documents/999 should return 404."""
        response = test_client.get("/documents/99999")

        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"

    def test_update_document_status(self, test_client: TestClient, sample_document: Document):
        """PATCH /documents/{id} should update status."""
        response = test_client.patch(
            f"/documents/{sample_document.id}",
            json={"status": "Controlled"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Controlled"

    def test_invalid_status_transition(self, test_client: TestClient, sample_document: Document):
        """PATCH cannot transition from Controlled back to Draft."""
        # First, transition to Controlled
        test_client.patch(
            f"/documents/{sample_document.id}",
            json={"status": "Controlled"}
        )

        # Try to transition back to Draft
        response = test_client.patch(
            f"/documents/{sample_document.id}",
            json={"status": "Draft"}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INVALID_TRANSITION"

    def test_update_document_version(self, test_client: TestClient, sample_document: Document):
        """PATCH /documents/{id} should update version."""
        response = test_client.patch(
            f"/documents/{sample_document.id}",
            json={"version": "v1.1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1.1"

    def test_delete_document(self, test_client: TestClient, sample_document: Document):
        """DELETE /documents/{id} should soft delete (set status=Obsolete)."""
        response = test_client.delete(f"/documents/{sample_document.id}")

        assert response.status_code == 204

        # Verify document still exists with Obsolete status
        get_response = test_client.get(f"/documents/{sample_document.id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "Obsolete"

    def test_get_document_with_tasks(
        self, test_client: TestClient, sample_document: Document, multiple_tasks: list[Task]
    ):
        """GET /documents/{id}/tasks should include document and tasks."""
        response = test_client.get(f"/documents/{sample_document.id}/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "document" in data
        assert "tasks" in data
        assert data["document"]["id"] == sample_document.id
        assert len(data["tasks"]) == 3


# ============================================================================
# Task Endpoint Tests
# ============================================================================

class TestTaskEndpoints:
    """Integration tests for /tasks endpoints."""

    def test_bulk_create_tasks(self, test_client: TestClient, sample_document: Document):
        """POST /tasks with array should create multiple tasks."""
        tasks_data = {
            "tasks": [
                {
                    "document_id": sample_document.id,
                    "task_description": "Task 1",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                    "priority": "Critical",
                },
                {
                    "document_id": sample_document.id,
                    "task_description": "Task 2",
                    "iso_clause": "7.2",
                    "assigned_department": "Milling",
                    "priority": "High",
                },
            ]
        }

        response = test_client.post("/tasks", json=tasks_data)

        assert response.status_code == 201
        data = response.json()
        assert data["created_count"] == 2
        assert len(data["task_ids"]) == 2

    def test_create_task_without_iso_clause_fails(
        self, test_client: TestClient, sample_document: Document
    ):
        """POST /tasks without iso_clause should return 422."""
        tasks_data = {
            "tasks": [
                {
                    "document_id": sample_document.id,
                    "task_description": "Task without ISO",
                    # Missing iso_clause
                    "assigned_department": "Quality",
                }
            ]
        }

        response = test_client.post("/tasks", json=tasks_data)

        assert response.status_code == 422

    def test_create_task_empty_iso_clause_fails(
        self, test_client: TestClient, sample_document: Document
    ):
        """POST /tasks with empty iso_clause should return 422."""
        tasks_data = {
            "tasks": [
                {
                    "document_id": sample_document.id,
                    "task_description": "Task with empty ISO",
                    "iso_clause": "",
                    "assigned_department": "Quality",
                }
            ]
        }

        response = test_client.post("/tasks", json=tasks_data)

        assert response.status_code == 422

    def test_create_task_invalid_document_id(self, test_client: TestClient):
        """POST /tasks with non-existent document_id should return 404."""
        tasks_data = {
            "tasks": [
                {
                    "document_id": 99999,
                    "task_description": "Orphan task",
                    "iso_clause": "8.5.1",
                    "assigned_department": "Quality",
                }
            ]
        }

        response = test_client.post("/tasks", json=tasks_data)

        assert response.status_code == 404

    def test_get_tasks(self, test_client: TestClient, multiple_tasks: list[Task]):
        """GET /tasks should return list of tasks."""
        response = test_client.get("/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    def test_get_tasks_by_department(self, test_client: TestClient, multiple_tasks: list[Task]):
        """GET /tasks?department=Quality should filter results."""
        response = test_client.get("/tasks", params={"department": "Quality"})

        assert response.status_code == 200
        data = response.json()
        for task in data:
            assert task["assigned_department"] == "Quality"

    def test_get_tasks_by_priority(self, test_client: TestClient, multiple_tasks: list[Task]):
        """GET /tasks?priority=Critical should filter results."""
        response = test_client.get("/tasks", params={"priority": "Critical"})

        assert response.status_code == 200
        data = response.json()
        for task in data:
            assert task["priority"] == "Critical"

    def test_get_tasks_by_status(self, test_client: TestClient, multiple_tasks: list[Task]):
        """GET /tasks?status=Pending should filter results."""
        response = test_client.get("/tasks", params={"status": "Pending"})

        assert response.status_code == 200
        data = response.json()
        for task in data:
            assert task["status"] == "Pending"

    def test_get_tasks_by_document_id(
        self, test_client: TestClient, sample_document: Document, multiple_tasks: list[Task]
    ):
        """GET /tasks?document_id={id} should filter results."""
        response = test_client.get("/tasks", params={"document_id": sample_document.id})

        assert response.status_code == 200
        data = response.json()
        for task in data:
            assert task["document_id"] == sample_document.id

    def test_get_task_by_id(self, test_client: TestClient, sample_task: Task):
        """GET /tasks/{id} should return single task."""
        response = test_client.get(f"/tasks/{sample_task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_task.id
        assert data["iso_clause"] == sample_task.iso_clause

    def test_get_task_not_found(self, test_client: TestClient):
        """GET /tasks/99999 should return 404."""
        response = test_client.get("/tasks/99999")

        assert response.status_code == 404

    def test_update_task_status(self, test_client: TestClient, sample_task: Task):
        """PATCH /tasks/{id} should update status."""
        response = test_client.patch(
            f"/tasks/{sample_task.id}",
            json={"status": "Completed"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Completed"

    def test_update_task_priority(self, test_client: TestClient, sample_task: Task):
        """PATCH /tasks/{id} should update priority."""
        response = test_client.patch(
            f"/tasks/{sample_task.id}",
            json={"priority": "Critical"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == "Critical"

    def test_update_task_assigned_role(self, test_client: TestClient, sample_task: Task):
        """PATCH /tasks/{id} should update assigned_role."""
        response = test_client.patch(
            f"/tasks/{sample_task.id}",
            json={"assigned_role": "Senior Inspector"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["assigned_role"] == "Senior Inspector"


# ============================================================================
# System Endpoint Tests
# ============================================================================

class TestSystemEndpoints:
    """Integration tests for system endpoints."""

    def test_health_check(self, test_client: TestClient):
        """GET /health should return health status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_audit_trail(self, test_client: TestClient, sample_document: Document):
        """GET /audit-trail/{id} should return audit entries."""
        response = test_client.get(f"/audit-trail/{sample_document.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["document_id"] == sample_document.id

    def test_audit_trail_not_found(self, test_client: TestClient):
        """GET /audit-trail/99999 should return 404."""
        response = test_client.get("/audit-trail/99999")

        assert response.status_code == 404
