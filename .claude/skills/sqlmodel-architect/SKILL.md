---
name: sqlmodel-architect
description: SQLModel database architecture for Rice Export FSMS with ISO 22001:2018 compliance. Use when creating SQLModel models, setting up Neon Postgres connections, or implementing Document/Task tables for the rice mill food safety management system. Triggers on database schema design, model creation, or compliance data structure tasks.
---

# SQLModel Architect

Database architecture skill for Rice Export FSMS. Generates SQLModel models with ISO 22001:2018 compliance features including tamper detection, audit trails, and document control.

## Quick Start

1. Read the templates from `references/` directory
2. Generate `models.py` and `database.py` in project root
3. Run table creation

```python
from database import create_tables, health_check
from models import Document, Task

# Verify connection
print(health_check())

# Create tables
create_tables()
```

## Core Models

### Document Model

Controlled document tracking for ISO 22001:2018.

| Field | Type | Constraints |
|-------|------|-------------|
| id | int | PK, auto-increment |
| doc_id | str | unique, indexed (e.g., "FSMS-SOP-001") |
| title | str | required |
| department | str | enum: Milling, Quality, Exports, Packaging, Storage |
| version | str | pattern: `v\d+\.\d+` |
| status | str | enum: Draft → Controlled → Obsolete |
| prepared_by | str | required (ISO compliance) |
| approved_by | str | required (ISO compliance) |
| record_keeper | str | required |
| approval_date | datetime | nullable |
| review_cycle_months | int | default: 12 |
| iso_clauses | str | JSON array of clause numbers |
| file_path | str | path to controlled document |
| file_hash | str | SHA-256 of file content |
| created_at | datetime | auto-set |
| updated_at | datetime | auto-update |
| version_hash | str | SHA-256 tamper detection |

### Task Model

Compliance tasks extracted from documents.

| Field | Type | Constraints |
|-------|------|-------------|
| id | int | PK, auto-increment |
| document_id | int | FK → document.id (CASCADE) |
| task_description | text | required |
| action | str | extracted verb |
| object | str | target object |
| iso_clause | str | **REQUIRED** - CHECK constraint |
| critical_limit | str | nullable (e.g., "14% max") |
| frequency | str | nullable (e.g., "Every 4 hours") |
| assigned_department | str | required |
| assigned_role | str | nullable |
| priority | str | enum: Critical, High, Medium, Low |
| status | str | enum: Pending, Completed, Overdue |
| source_document_version | str | locks to document version |
| extracted_from_page | int | nullable |
| created_at | datetime | auto-set |

## Validation Rules

### Version Format
```python
# Must match: v1.0, v1.1, v2.0, etc.
pattern = r'^v\d+\.\d+$'
```

### Status Transitions (One-Way)
```
Draft → Controlled → Obsolete
```
No backward transitions allowed.

### Department Validation
```python
VALID_DEPARTMENTS = ["Milling", "Quality", "Exports", "Packaging", "Storage"]
```

### ISO Clause Requirement
Task.iso_clause enforced at database level:
```sql
CHECK (iso_clause IS NOT NULL AND iso_clause != '')
```

## Database Connection

### Environment Setup
Create `.env` file:
```
DATABASE_URL=postgresql://user:pass@host/rice_fsms_db?sslmode=require
```

### Connection Features
- Pool size: 5 connections
- Max overflow: 10 connections
- SSL required for Neon
- Retry logic: 3 attempts with exponential backoff
- Pre-ping for connection validation

### Session Usage
```python
from database import get_session

with get_session() as session:
    doc = Document(
        doc_id="FSMS-SOP-001",
        title="Milling Procedures",
        department="Milling",
        version="v1.0",
        prepared_by="John Doe",
        approved_by="Jane Smith",
        record_keeper="QA Team"
    )
    session.add(doc)
    session.commit()
```

## Tamper Detection

### Document Hash
```python
# Automatic on insert/update
doc.update_version_hash()

# Verify integrity
computed = doc.compute_version_hash()
if computed != doc.version_hash:
    raise SecurityError("Document tampered")
```

### File Hash
```python
# Compute hash for controlled document file
file_hash = Document.compute_file_hash("/path/to/document.pdf")
doc.file_hash = file_hash
```

## References

- `references/models_template.py` - Complete Document and Task model implementations
- `references/database_template.py` - Database connection with pooling and retry logic

When generating code, read these templates and adapt to the project's specific requirements.
