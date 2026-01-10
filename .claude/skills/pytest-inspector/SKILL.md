---
name: pytest-inspector
description: Pytest test generation for Rice Export FSMS with async support, fixtures, and coverage. Use when writing tests for SQLModel models, FastAPI endpoints, or validating ISO 22001:2018 compliance workflows. Triggers on test creation, test running, coverage reports, or QA tasks.
---

# Pytest Inspector

Test generation skill for Rice Export FSMS. Creates unit tests, integration tests, and end-to-end workflow tests with pytest fixtures and coverage reporting.

## Quick Start

```bash
# Install dependencies
uv add pytest pytest-asyncio pytest-cov httpx

# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific file
uv run pytest tests/test_models.py -v

# Run specific test
uv run pytest tests/test_api.py::TestDocumentEndpoints::test_create_document_success -v
```

## Test Structure

```
tests/
├── conftest.py      # Fixtures and setup
├── test_models.py   # Unit tests for SQLModel
├── test_api.py      # Integration tests for FastAPI
└── test_workflow.py # End-to-end workflow tests
```

## Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_db` | function | Clean database session per test |
| `test_client` | function | FastAPI TestClient with test DB |
| `sample_document` | function | Pre-created Document fixture |
| `sample_task` | function | Pre-created Task fixture |
| `multiple_documents` | function | 3 documents for filter testing |
| `multiple_tasks` | function | 3 tasks for filter testing |

## Test Categories

### Unit Tests (test_models.py)

| Test | Validates |
|------|-----------|
| `test_document_requires_ownership_fields` | prepared_by, approved_by, record_keeper |
| `test_task_requires_iso_clause` | iso_clause cannot be empty |
| `test_version_format_validation` | v\\d+\\.\\d+ pattern |
| `test_status_enum_validation` | Draft, Controlled, Obsolete |
| `test_department_enum_validation` | Valid department list |
| `test_document_task_relationship` | 1:N relationship |
| `test_cascade_delete` | CASCADE delete behavior |

### Integration Tests (test_api.py)

**Document Endpoints:**
- `test_create_document_success` - POST /documents
- `test_create_document_duplicate_doc_id` - 400 on duplicate
- `test_get_documents_filter_by_department` - Query params
- `test_invalid_status_transition` - 400 on Draft←Controlled
- `test_delete_document` - Soft delete → Obsolete

**Task Endpoints:**
- `test_bulk_create_tasks` - POST /tasks with array
- `test_create_task_without_iso_clause_fails` - 422 validation
- `test_get_tasks_by_priority` - Filter by priority
- `test_update_task_status` - PATCH status change

### End-to-End Tests (test_workflow.py)

| Test | Scenario |
|------|----------|
| `test_full_document_lifecycle` | Draft → Controlled → Add Tasks |
| `test_document_deletion_cascades_to_tasks` | Soft delete preserves tasks |
| `test_duplicate_prevention` | Cannot create duplicate doc_id |
| `test_version_progression` | v1.0 → v1.1 → v2.0 |
| `test_iso_compliance_workflow` | Ownership fields enforced |
| `test_status_transition_compliance` | One-way transitions |

## Test Database Setup

Add to `.env`:
```
DATABASE_URL_TEST=postgresql://user:pass@host/rice_fsms_db_test?sslmode=require
```

Or use in-memory SQLite (default fallback):
```python
DATABASE_URL_TEST = os.getenv("DATABASE_URL_TEST", "sqlite:///:memory:")
```

## Coverage Target

- Aim for 80%+ coverage
- HTML report: `htmlcov/index.html`

```bash
uv run pytest --cov=. --cov-report=html --cov-fail-under=80
```

## References

- `references/conftest_template.py` - Fixture definitions
- `references/test_models_template.py` - Unit tests
- `references/test_api_template.py` - Integration tests
- `references/test_workflow_template.py` - E2E tests

When generating tests, read templates and adapt to specific requirements.
