# Rice Export FSMS - Prompt-Based Instruction Manual

## Quick Reference: Files & Skills

| Step | Skill | Python File | API Endpoint |
|------|-------|-------------|--------------|
| Gap Analysis | `/iso-gap-analyzer` | `gap_analyzer.py` | `GET /documents/{id}/gap-analysis` |
| Document Control | `/doc-controller` | `doc_controller.py` | `PATCH /documents/{id}` |
| Task Extraction | `/fsms-task-extractor` | `task_extractor.py` | `POST /tasks` |
| PDF Reading | `/pdf` | - | - |
| DOCX Reading | `/docx` | - | - |

---

## SCENARIO 1: New Document - Complete Workflow

### PROMPT 1.1: Upload & Create Record

```
I have placed a new document at documents/raw/Rice_Milling_SOP.pdf

Using main.py (FastAPI running on port 8000), create a document record:
- doc_id: FSMS-SOP-001
- title: Rice Milling Standard Operating Procedure
- department: Milling
- version: v0.1
- file_path: documents/raw/Rice_Milling_SOP.pdf

Leave prepared_by, approved_by, record_keeper empty for now.
Use POST /documents endpoint.
```

### PROMPT 1.2: Run Gap Analysis

```
Using the /iso-gap-analyzer skill and gap_analyzer.py:

1. Read documents/raw/Rice_Milling_SOP.pdf using /pdf skill
2. Fetch document record FSMS-SOP-001 from GET /documents endpoint
3. Run gap analysis using gap_analyzer.py functions:
   - DocumentClassifier().classify() to determine document type
   - GapAnalyzer().analyze() to check ISO 22001:2018 compliance
4. Check these ISO clauses from iso_22001_clauses.py:
   - Clause 7.5.2: Document creation (prepared_by, approved_by)
   - Clause 7.5.3: Document control (status, version)
   - Clause 8.5.1: Hazard control
5. Return gap report with compliance score and missing fields
```

### PROMPT 1.3: Fix Gaps - Update Document

```
Using main.py API (PATCH /documents/{id}), update document FSMS-SOP-001:

{
  "prepared_by": "Quality Manager - Ahmad Khan",
  "approved_by": "Plant Director - Dr. Fatima Ali",
  "record_keeper": "Document Control - Zainab Hassan"
}

Then re-run gap analysis using /iso-gap-analyzer to confirm score is now 100%.
```

### PROMPT 1.4: Approve Document

```
Using the /doc-controller skill and doc_controller.py:

1. Fetch document FSMS-SOP-001 from API
2. Run validate_prerequisites() from doc_controller.py to check:
   - prepared_by is not empty
   - approved_by is not empty
   - record_keeper is not empty
   - status is "Draft" (not "Obsolete")
3. If validation passes:
   - Calculate SHA-256 hash using Document.compute_file_hash() from models.py
   - Move file: documents/raw/Rice_Milling_SOP.pdf → documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf
   - Set read-only permissions
4. Update database via PATCH /documents/{id}:
   - status: "Controlled"
   - version: "v1.0"
   - approval_date: current timestamp
   - file_path: new controlled path
   - file_hash: computed SHA-256
5. Log to audit_log.txt
6. Return approval confirmation
```

### PROMPT 1.5: Extract Tasks

```
Using the /fsms-task-extractor skill and task_extractor.py:

1. Read documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf using /pdf skill
2. Use TaskExtractor class from task_extractor.py to:
   - Find all sentences containing "shall", "must", "is required to", "responsible for"
   - Parse each sentence to extract:
     - actor (who)
     - action (verb)
     - object (what)
     - frequency (how often)
     - critical_limit (threshold values like "14%", "<35°C")
3. Map each task using mappings from task_extractor.py:
   - Actor → Department (e.g., "operator" → "Milling")
   - Actor → Role (e.g., "operator" → "Operator")
   - Keywords → ISO clause (e.g., "monitor" → "8.5.1.3")
   - Conditions → Priority (e.g., has critical_limit → "Critical")
4. Create tasks via POST /tasks endpoint from main.py
5. Return extraction report with task count by department and priority
```

---

## SCENARIO 2: Gap Analysis Only (No Approval)

### PROMPT 2.1: Quick Gap Check

```
Using /iso-gap-analyzer skill with gap_analyzer.py and iso_22001_clauses.py:

Analyze documents/raw/New_Procedure.pdf for ISO 22001:2018 gaps WITHOUT creating a database record.

1. Use /pdf skill to extract text
2. Use DocumentClassifier from gap_analyzer.py to classify as:
   - POLICY (contains "policy", "commitment")
   - SOP (contains "procedure", "shall", step-by-step)
   - PROCESS_FLOW (contains "flowchart", "diagram")
   - RECORD (contains "log", "checklist", "form")
3. Check required fields per document type from iso_22001_clauses.py
4. Check for rice mill hazards:
   - Physical: stones, metal, glass
   - Chemical: pesticides, aflatoxin, fumigants
   - Biological: mold, insects, rodents
5. Return gap report with:
   - Document type classification
   - Compliance score (0-100%)
   - Missing required elements
   - Recommendations to fix gaps
```

---

## SCENARIO 3: Document Version Update

### PROMPT 3.1: Minor Update (Typo Fix)

```
Using /doc-controller skill with doc_controller.py:

Document FSMS-SOP-001 (currently v1.0, Controlled) has a typo fix.
New file is at documents/raw/Rice_Milling_SOP_v1.1.pdf

This is a MINOR change. Please:

1. Use VersionInfo class from doc_controller.py to increment: v1.0 → v1.1
2. Archive current controlled file:
   - Move documents/controlled/FSMS-SOP-001_v1.0_...
   - To documents/archive/FSMS-SOP-001_v1.0_ARCHIVED_20250110.pdf
3. Process new file:
   - Compute SHA-256 hash
   - Move to documents/controlled/FSMS-SOP-001_v1.1_Rice_Milling_SOP.pdf
   - Set read-only
4. Update database via PATCH /documents/{id}:
   - version: "v1.1"
   - file_path: new path
   - file_hash: new hash
   - updated_at: current timestamp
5. Log version change to audit_log.txt
6. DO NOT re-extract tasks (minor change)
```

### PROMPT 3.2: Major Update (Process Change)

```
Using /doc-controller skill with doc_controller.py and /fsms-task-extractor skill:

Document FSMS-SOP-001 (currently v1.1, Controlled) has MAJOR process changes.
New file is at documents/raw/Rice_Milling_SOP_v2.pdf

This is a MAJOR change (new CCPs, changed critical limits). Please:

1. Use VersionInfo from doc_controller.py to increment: v1.1 → v2.0
2. Archive current version to documents/archive/
3. Run gap analysis on new file using gap_analyzer.py
4. If gaps are fixed:
   - Compute new hash using models.py Document.compute_file_hash()
   - Move to documents/controlled/FSMS-SOP-001_v2.0_Rice_Milling_SOP.pdf
5. Update database via PATCH /documents/{id}:
   - version: "v2.0"
   - file_path, file_hash, updated_at
6. Mark old tasks as obsolete or delete them
7. Re-extract tasks using task_extractor.py TaskExtractor class
8. Create new tasks via POST /tasks
9. Return version update report and new task count
```

---

## SCENARIO 4: View & Query Data

### PROMPT 4.1: List All Controlled Documents

```
Using main.py API, query all controlled documents:

GET /documents?status=Controlled

Return a table showing:
- doc_id
- title
- department
- version
- approval_date
```

### PROMPT 4.2: Get Document with Tasks

```
Using main.py API, get document FSMS-SOP-001 with all its tasks:

GET /documents/1/tasks

Return:
- Document details (doc_id, title, version, status)
- List of tasks with:
  - task_description
  - frequency
  - critical_limit
  - priority
  - assigned_department
```

### PROMPT 4.3: Filter Tasks by Priority

```
Using main.py API, get all Critical priority tasks:

GET /tasks?priority=Critical

Return tasks grouped by department showing:
- task_description
- document doc_id
- frequency
- critical_limit
```

---

## SCENARIO 5: Database Operations

### PROMPT 5.1: Verify Database Tables

```
Using database.py and models.py:

1. Call health_check() from database.py to verify connection
2. Use create_tables() to ensure tables exist
3. Query document and task tables to show:
   - Total document count
   - Documents by status (Draft, Controlled, Obsolete)
   - Total task count
   - Tasks by priority
```

### PROMPT 5.2: Check Document Integrity

```
Using models.py Document class:

For document FSMS-SOP-001:
1. Fetch from database
2. Recompute version_hash using compute_version_hash()
3. Compare with stored version_hash
4. Recompute file_hash using compute_file_hash() on the actual file
5. Compare with stored file_hash
6. Report if any hash mismatch (indicates tampering)
```

---

## SCENARIO 6: Bulk Operations

### PROMPT 6.1: Bulk Task Creation

```
Using main.py API and task_extractor.py:

I have these tasks to create for document ID 1:

1. "Operator shall check moisture every 4 hours" - Critical
2. "Inspector shall verify temperature per batch" - Critical
3. "Technician shall calibrate meters weekly" - High

Use TaskExtractor from task_extractor.py to parse each sentence, then:

POST /tasks with bulk payload:
{
  "tasks": [
    {
      "document_id": 1,
      "task_description": "...",
      "action": "...",
      "object": "...",
      "iso_clause": "...",
      "frequency": "...",
      "critical_limit": "...",
      "assigned_department": "...",
      "assigned_role": "...",
      "priority": "...",
      "source_document_version": "v1.0"
    },
    ...
  ]
}
```

---

## SCENARIO 7: Troubleshooting

### PROMPT 7.1: Debug Gap Analysis

```
Using gap_analyzer.py and iso_22001_clauses.py:

Gap analysis for FSMS-SOP-001 shows 60% compliance but I've filled all fields.

Debug by:
1. Fetch document from GET /documents/{id}
2. Print all field values
3. Check each against REQUIRED_FIELDS in iso_22001_clauses.py
4. Identify which fields are empty string "" vs proper values
5. Check if document content has required elements using GapAnalyzer
6. Show exactly what's missing and why score isn't 100%
```

### PROMPT 7.2: Debug Task Extraction

```
Using task_extractor.py:

Task extraction found 0 tasks in FSMS-SOP-001.

Debug by:
1. Read document using /pdf skill, show first 500 characters
2. Search for "shall", "must", "required" in text
3. If found, show the full sentences
4. Run TaskExtractor.extract_mandatory_sentences() and show results
5. If not found, report that document lacks mandatory statements
```

### PROMPT 7.3: Fix Status Transition Error

```
Using models.py STATUS_TRANSITIONS:

Cannot change document status from "Controlled" to "Draft".

Explain using STATUS_TRANSITIONS dict from models.py:
- Draft → Controlled (allowed)
- Controlled → Obsolete (allowed)
- Obsolete → nothing (terminal state)

Status transitions are ONE-WAY only per ISO 7.5.3.
To "revert", create a new document version instead.
```

---

## Complete Single Prompts

### PROMPT A: Full Workflow in One Request

```
I uploaded documents/raw/Paddy_Storage_SOP.pdf

Please complete the full FSMS workflow:

1. CREATE RECORD (main.py POST /documents):
   - doc_id: FSMS-SOP-003
   - title: Paddy Storage Procedure
   - department: Storage
   - version: v0.1
   - prepared_by: Storage Manager - Imran Ali
   - approved_by: Plant Director - Dr. Fatima Ali
   - record_keeper: Document Control - Zainab Hassan

2. GAP ANALYSIS (/iso-gap-analyzer skill, gap_analyzer.py):
   - Read PDF using /pdf skill
   - Classify document type
   - Check ISO 22001:2018 compliance
   - Report any gaps

3. IF NO GAPS - APPROVE (/doc-controller skill, doc_controller.py):
   - Validate prerequisites
   - Compute SHA-256 hash (models.py)
   - Move to documents/controlled/FSMS-SOP-003_v1.0_Paddy_Storage_SOP.pdf
   - Update database: status=Controlled, version=v1.0
   - Log to audit trail

4. EXTRACT TASKS (/fsms-task-extractor skill, task_extractor.py):
   - Parse "shall"/"must" statements
   - Map to departments and ISO clauses
   - Assign priorities
   - Create via POST /tasks

5. REPORT:
   - Document status
   - Compliance score
   - Number of tasks extracted by department
   - Task IDs created
```

### PROMPT B: Quick Status Check

```
Using main.py API and database.py:

Give me a status report:

1. GET /health - Database connection status
2. GET /documents - Count by status (Draft/Controlled/Obsolete)
3. GET /tasks - Count by priority (Critical/High/Medium/Low)
4. List any documents in Draft status that need attention
5. List Critical tasks that are Pending
```

### PROMPT C: Document Audit

```
Using models.py, doc_controller.py, and main.py API:

Audit document FSMS-SOP-001:

1. Fetch document record from API
2. Verify file exists at file_path
3. Recompute file_hash and compare with stored hash
4. Recompute version_hash and compare with stored hash
5. Check audit_log.txt for all entries related to this document
6. List all tasks linked to this document
7. Report:
   - File integrity: PASS/FAIL
   - Record integrity: PASS/FAIL
   - Task count
   - Last modified date
   - Version history
```

---

## Python File Reference

| File | Classes/Functions | Purpose |
|------|-------------------|---------|
| `models.py` | `Document`, `Task` | SQLModel database models |
| `models.py` | `VALID_DEPARTMENTS` | ["Milling", "Quality", "Exports", "Packaging", "Storage"] |
| `models.py` | `STATUS_TRANSITIONS` | Draft→Controlled→Obsolete |
| `models.py` | `Document.compute_file_hash()` | SHA-256 of file |
| `models.py` | `Document.compute_version_hash()` | SHA-256 of record |
| `database.py` | `get_session()` | Database session context manager |
| `database.py` | `health_check()` | Verify DB connection |
| `database.py` | `create_tables()` | Create document/task tables |
| `gap_analyzer.py` | `DocumentClassifier` | Classify doc type (Policy/SOP/etc) |
| `gap_analyzer.py` | `GapAnalyzer` | ISO 22001:2018 compliance check |
| `iso_22001_clauses.py` | `ISO_CLAUSES` | Clause definitions and requirements |
| `iso_22001_clauses.py` | `RICE_MILL_HAZARDS` | Physical/Chemical/Biological hazards |
| `doc_controller.py` | `DocumentController` | File operations, versioning |
| `doc_controller.py` | `VersionInfo` | Parse/increment versions |
| `doc_controller.py` | `validate_prerequisites()` | Check required fields |
| `task_extractor.py` | `TaskExtractor` | Parse "shall" statements |
| `task_extractor.py` | `ACTOR_DEPARTMENT_MAP` | Actor→Department mapping |
| `task_extractor.py` | `ISO_CLAUSE_MAP` | Keywords→ISO clause mapping |
| `main.py` | FastAPI app | All REST API endpoints |

---

## Skill Reference

| Skill | When to Use | What It Calls |
|-------|-------------|---------------|
| `/iso-gap-analyzer` | Check document compliance | `gap_analyzer.py`, `iso_22001_clauses.py` |
| `/doc-controller` | Approve/version documents | `doc_controller.py`, `models.py` |
| `/fsms-task-extractor` | Extract tasks from SOPs | `task_extractor.py`, `main.py` API |
| `/pdf` | Read PDF files | External PDF extraction |
| `/docx` | Read Word files | External DOCX extraction |

---

## API Endpoint Reference

| Endpoint | Method | Python Handler | Purpose |
|----------|--------|----------------|---------|
| `/health` | GET | `main.py:health_check()` | DB status |
| `/documents` | GET | `main.py:list_documents()` | List all docs |
| `/documents` | POST | `main.py:create_document()` | Create doc |
| `/documents/{id}` | GET | `main.py:get_document()` | Get one doc |
| `/documents/{id}` | PATCH | `main.py:update_document()` | Update doc |
| `/documents/{id}` | DELETE | `main.py:delete_document()` | Soft delete |
| `/documents/{id}/tasks` | GET | `main.py:get_document_with_tasks()` | Doc + tasks |
| `/tasks` | GET | `main.py:list_tasks()` | List tasks |
| `/tasks` | POST | `main.py:create_tasks()` | Bulk create |
| `/tasks/{id}` | GET | `main.py:get_task()` | Get one task |
| `/tasks/{id}` | PATCH | `main.py:update_task()` | Update task |
| `/audit-trail/{id}` | GET | `main.py:get_audit_trail()` | Version history |
