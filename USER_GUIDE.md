# Rice Export FSMS - User Guide

A complete Food Safety Management System (FSMS) for ISO 22001:2018 compliance, designed for rice mill operations.

## System Overview

This FSMS provides a digital document control and task management system that:
- Manages controlled documents with version control
- Analyzes documents for ISO 22001:2018 compliance gaps
- Extracts operational tasks from approved SOPs
- Maintains audit trails for regulatory compliance

## Quick Start

### 1. Start the API Server

```bash
uv run fastapi dev main.py --port 8000
```

Access the API documentation at: http://localhost:8000/docs

### 2. Verify Database Connection

```bash
curl http://localhost:8000/health
```

## Complete FSMS Workflow

```
[Upload Document] → [Gap Analysis] → [Fix Gaps] → [Approve] → [Extract Tasks]
     (Draft)         (ISO Check)     (Update)    (Controlled)   (Operational)
```

### Step 1: Upload a Document

Place your document file in `documents/raw/` folder:
```bash
mkdir -p documents/raw documents/controlled documents/archive
cp your-sop.pdf documents/raw/
```

Create the document record via API:
```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "FSMS-SOP-001",
    "title": "Rice Milling Procedure",
    "doc_type": "SOP",
    "department": "Milling",
    "file_path": "documents/raw/your-sop.pdf"
  }'
```

### Step 2: Run Gap Analysis

Use the **iso-gap-analyzer** skill:
```
/iso-gap-analyzer FSMS-SOP-001
```

Or via API:
```bash
curl http://localhost:8000/documents/1/gap-analysis
```

The analyzer checks:
- Required ISO fields (prepared_by, approved_by, etc.)
- Document classification (Policy, SOP, Process Flow, Record)
- Rice mill specific hazards (Physical, Chemical, Biological)
- Compliance score (0-100%)

### Step 3: Fix Identified Gaps

Update the document with missing fields:
```bash
curl -X PATCH http://localhost:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "prepared_by": "Quality Manager",
    "approved_by": "Plant Director",
    "effective_date": "2025-01-15",
    "review_date": "2026-01-15",
    "scope": "Covers all milling operations from paddy intake to white rice output"
  }'
```

### Step 4: Approve Document

Use the **doc-controller** skill:
```
/doc-controller approve FSMS-SOP-001
```

This will:
- Validate all required fields are present
- Move file from `raw/` to `controlled/`
- Rename with version: `FSMS-SOP-001_v1.0_Rice_Milling_Procedure.pdf`
- Set read-only permissions
- Calculate SHA-256 hash for tamper detection
- Update status to "Controlled"
- Log to audit trail

### Step 5: Extract Operational Tasks

Use the **fsms-task-extractor** skill:
```
/fsms-task-extractor FSMS-SOP-001
```

This extracts tasks from "shall" and "must" statements:

**Example SOP text:**
```
"The operator shall check rice moisture content every 4 hours using a calibrated moisture meter."
```

**Extracted Task:**
| Field | Value |
|-------|-------|
| action | check |
| object | rice moisture content |
| frequency | Every 4 hours |
| assigned_department | Milling |
| assigned_role | Operator |
| iso_clause | 8.5.1.3 |
| priority | Critical |

## API Quick Reference

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List all documents |
| GET | `/documents/{id}` | Get document by ID |
| POST | `/documents` | Create new document |
| PATCH | `/documents/{id}` | Update document |
| DELETE | `/documents/{id}` | Delete document |
| GET | `/documents/{id}/gap-analysis` | Run ISO gap analysis |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{id}` | Get task by ID |
| POST | `/tasks` | Create new task |
| PATCH | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |
| GET | `/documents/{id}/tasks` | Get tasks for document |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/stats` | System statistics |

## Skills Reference

| Skill | When to Use |
|-------|-------------|
| **sqlmodel-architect** | Database schema design, model creation |
| **fastapi-route-wizard** | API endpoint generation |
| **pytest-inspector** | Test creation and running |
| **iso-gap-analyzer** | Document compliance checking |
| **doc-controller** | Document approval and versioning |
| **fsms-task-extractor** | Task extraction from SOPs |

## ISO 22001:2018 Clause Mapping

| Clause | Topic | System Feature |
|--------|-------|----------------|
| 5.2 | Policy | Policy document type |
| 5.3 | Roles | Department and role assignments |
| 7.5.2 | Document Creation | prepared_by, created_at |
| 7.5.3 | Document Control | status, version, approval workflow |
| 8.1 | Operational Planning | Process flow documents |
| 8.5.1 | Hazard Control | Task extraction with hazard mapping |
| 8.5.1.2 | Critical Limits | critical_limit field extraction |
| 8.5.1.3 | Monitoring | frequency field extraction |

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py -v
```

## Folder Structure

```
rice_mill_fsms/
├── main.py                 # FastAPI application
├── models.py               # SQLModel database models
├── database.py             # Database connection
├── gap_analyzer.py         # ISO compliance analyzer
├── iso_22001_clauses.py    # ISO clause definitions
├── doc_controller.py       # Document version control
├── task_extractor.py       # Task extraction logic
├── documents/
│   ├── raw/                # Draft documents
│   ├── controlled/         # Approved documents
│   └── archive/            # Obsoleted versions
├── tests/
│   ├── conftest.py         # Test fixtures
│   ├── test_models.py      # Model tests
│   ├── test_api.py         # API tests
│   └── test_workflow.py    # E2E workflow tests
└── .claude/skills/         # Custom Claude skills
```

## Document Status Transitions

```
Draft → Controlled → Obsolete
  │         │
  │         └── Only via new version approval
  └── Via approval workflow
```

**Status Rules:**
- `Draft`: Initial state, can be edited freely
- `Controlled`: Approved, read-only, master copy
- `Obsolete`: Archived, retained for audit trail

## Priority Levels

| Priority | Trigger Conditions |
|----------|-------------------|
| **Critical** | Has critical_limit + halting action |
| **High** | Monitoring task + frequent schedule |
| **Medium** | Daily/weekly tasks |
| **Low** | Monthly+ reviews |

## Troubleshooting

### Database Connection Issues
```bash
# Check connection
curl http://localhost:8000/health

# Verify tables exist
uv run python -c "from database import create_tables; create_tables()"
```

### File Permission Issues
```bash
# Set correct permissions on folders
chmod 755 documents/raw documents/controlled documents/archive
```

### API Not Starting
```bash
# Check if port is in use
lsof -i :8000

# Use different port
uv run fastapi dev main.py --port 8001
```

## Environment Variables

Create `.env` file in project root:
```env
DATABASE_URL=postgresql://user:password@host:5432/rice_fsms_db
```

## License

This FSMS is designed for ISO 22001:2018 compliance in rice export operations.
