---
name: fastapi-route-wizard
description: FastAPI route generation for Rice Export FSMS with async endpoints, Pydantic validation, and OpenAPI docs. Use when creating API routes, CRUD endpoints, or REST services for the food safety management system. Triggers on API development, endpoint creation, route implementation, or FastAPI tasks.
---

# FastAPI Route Wizard

Generates FastAPI endpoints for Rice Export FSMS. Includes Document/Task CRUD, validation, audit trails, and automatic OpenAPI documentation.

## Quick Start

```bash
# Install dependencies (includes uvicorn, httptools, email-validator, etc.)
uv add "fastapi[standard]"

# Run server (development mode with auto-reload)
uv run fastapi dev main.py --port 8000

# Or production mode
uv run fastapi run main.py --port 8000

# Access docs
# http://localhost:8000/docs
```

## Endpoints Reference

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents` | Create document |
| GET | `/documents` | List with filters |
| GET | `/documents/{id}` | Get by ID |
| PATCH | `/documents/{id}` | Update fields |
| DELETE | `/documents/{id}` | Soft delete (→ Obsolete) |
| GET | `/documents/{id}/tasks` | Get with tasks |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Bulk create |
| GET | `/tasks` | List with filters |
| GET | `/tasks/{id}` | Get by ID |
| PATCH | `/tasks/{id}` | Update fields |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Database health |
| GET | `/audit-trail/{doc_id}` | Version history |

## Request/Response Examples

### Create Document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "FSMS-SOP-001",
    "title": "Milling Procedures",
    "department": "Milling",
    "version": "v1.0",
    "prepared_by": "Quality Manager",
    "approved_by": "Plant Director",
    "record_keeper": "Document Control"
  }'
```

### List Documents with Filters

```bash
curl "http://localhost:8000/documents?department=Quality&status=Draft&limit=10"
```

### Update Document Status

```bash
curl -X PATCH http://localhost:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "Controlled"}'
```

### Bulk Create Tasks

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {
        "document_id": 1,
        "task_description": "Check moisture content of paddy",
        "iso_clause": "8.5.1",
        "assigned_department": "Quality",
        "priority": "Critical",
        "critical_limit": "14% max"
      }
    ]
  }'
```

## Validation Rules

### Document

| Field | Validation |
|-------|------------|
| doc_id | Unique |
| version | Pattern: `v\d+\.\d+` |
| department | Enum: Milling, Quality, Exports, Packaging, Storage |
| status | Transitions: Draft → Controlled → Obsolete |

### Task

| Field | Validation |
|-------|------------|
| iso_clause | Required, non-empty |
| priority | Enum: Critical, High, Medium, Low |
| status | Enum: Pending, Completed, Overdue |

## Error Responses

```json
{
  "error_code": "INVALID_TRANSITION",
  "detail": "Cannot transition from 'Controlled' to 'Draft'"
}
```

| Code | Status | Meaning |
|------|--------|---------|
| DUPLICATE_DOC_ID | 400 | doc_id already exists |
| INVALID_TRANSITION | 400 | Status transition not allowed |
| NOT_FOUND | 404 | Resource doesn't exist |
| INTERNAL_ERROR | 500 | Database/server error |

## CORS Configuration

Default development settings:
- Origins: `["*"]`
- Methods: `["GET", "POST", "PATCH", "DELETE"]`
- Headers: `["*"]`

## Dependencies

```python
from database import get_session
from models import Document, Task, VALID_DEPARTMENTS, STATUS_TRANSITIONS
```

Requires:
- `models.py` with Document/Task SQLModel models
- `database.py` with get_session context manager

## References

- `references/main_template.py` - Complete FastAPI application template

When generating code, read the template and adapt to specific requirements.
