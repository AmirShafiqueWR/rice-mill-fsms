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

2. First, analyze document context using analyze_document_context(text):
   - Detect document type (SOP, Policy, etc.)
   - Identify primary department from content
   - Find all actors mentioned
   - List unmapped actors (not in task_extractor_config.json)

3. Use extract_tasks_from_text(text, config) to:
   - Find all sentences containing "shall", "must", "is required to", "responsible for"
   - Parse each sentence to extract:
     - actor (who)
     - action (verb)
     - object (what)
     - frequency (how often)
     - critical_limit (threshold values like "14%", "<35°C")

4. Map each task using ExtractorConfig (from task_extractor_config.json or defaults):
   - If actor is in config → Use mapped Department/Role (100% confidence)
   - If actor NOT in config → Infer from keywords (70% confidence, marked [INFERRED])
   - If still no match → Use document's primary department as fallback

5. For unmapped actors, call suggest_actor_mappings(context) to get suggestions

6. Create tasks via POST /tasks endpoint from main.py

7. Return ExtractionResult showing:
   - Task count by department and priority
   - detected_actors: All actors found in document
   - suggested_mappings: Recommendations for unmapped actors
   - Number of inferred vs mapped tasks
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

## SCENARIO 8: Configurable Task Extraction (SOP-Dependent)

The task_extractor.py now adapts to each SOP's content instead of using only hardcoded mappings.

### PROMPT 8.1: Preview Extraction Before Saving

```
Using task_extractor.py preview_extraction():

I have a new SOP at documents/controlled/FSMS-SOP-005_v1.0_Fumigation.pdf

Before extracting tasks to database, preview what will be extracted:

1. Read PDF using /pdf skill
2. Call preview_extraction(text) from task_extractor.py
3. Show me:
   - Document context (type, primary department)
   - All actors found in document
   - Unmapped actors (not in config)
   - Each extracted task with:
     - Sentence
     - Actor → Department/Role mapping
     - Confidence score (100% = mapped, 70% = inferred)
     - [INFERRED] marker if department was guessed
   - Suggested mappings for unmapped actors

DO NOT save to database yet. Just preview.
```

### PROMPT 8.2: Add Custom Actor Mappings

```
Using task_extractor.py ExtractorConfig:

The SOP uses actors not in the default mapping:
- "fumigation specialist" should map to Milling/Fumigation Specialist
- "rice grader" should map to Quality/Rice Grader
- "export coordinator" should map to Exports/Coordinator

1. Load config: ExtractorConfig.from_json("task_extractor_config.json")
2. Add mappings:
   config.add_actor_mapping("fumigation specialist", "Milling", "Fumigation Specialist")
   config.add_actor_mapping("rice grader", "Quality", "Rice Grader")
   config.add_actor_mapping("export coordinator", "Exports", "Coordinator")
3. Save config: config.to_json("task_extractor_config.json")
4. Re-run extraction with updated config
```

### PROMPT 8.3: Analyze Document Context

```
Using task_extractor.py analyze_document_context():

Analyze documents/raw/New_SOP.pdf to understand its context before extraction:

1. Read PDF using /pdf skill
2. Call analyze_document_context(text) from task_extractor.py
3. Return DocumentContext showing:
   - document_type: Policy/SOP/Process Flow/Record
   - primary_department: Most mentioned department
   - mentioned_departments: All departments referenced
   - unique_actors: All actors found (who "shall" do things)
   - unmapped_actors: Actors not in config
   - has_ccps: Whether document mentions CCPs
   - has_critical_limits: Whether document has threshold values

This helps understand what mappings might be needed before extraction.
```

### PROMPT 8.4: Extract with Auto-Added Mappings

```
Using task_extractor.py extract_and_create_tasks() with auto_add_mappings=True:

Extract tasks from FSMS-SOP-005 and automatically use suggested mappings for unmapped actors:

1. Read document using /pdf skill
2. Call extract_and_create_tasks(
     doc_id="FSMS-SOP-005",
     text=pdf_text,
     auto_add_mappings=True  # Auto-use suggestions
   )
3. This will:
   - Analyze document context
   - Find unmapped actors
   - Generate suggested mappings
   - Re-extract with suggestions applied
   - Create tasks in database
4. Return ExtractionResult showing:
   - Total tasks created
   - Tasks by department
   - detected_actors: All actors found
   - suggested_mappings: What was auto-applied
   - How many had inferred mappings
```

### PROMPT 8.5: Edit Configuration File Directly

```
The task_extractor_config.json file controls all mappings.

Show me the current config file and explain how to customize it:

1. Read task_extractor_config.json
2. Explain each section:
   - actor_department_map: {"actor": ["Department", "Role"]}
   - iso_clause_keywords: {"clause": ["keyword1", "keyword2"]}
   - priority_keywords: {"Critical": ["keyword1"], "High": [...]}
   - default_department: Fallback when no match
   - default_role: Fallback role
3. Show example of adding:
   - New actor mapping for this rice mill's specific roles
   - New ISO clause keywords
   - New priority keywords
```

### PROMPT 8.6: Handle Inferred Mappings in Report

```
Using task_extractor.py generate_extraction_report():

After extraction, some tasks show [INFERRED] with 70% confidence.

1. Generate extraction report using generate_extraction_report(result)
2. For each inferred mapping, the report will show:

   "Note: Some actors were not in the mapping config.
   Suggested mappings (add to task_extractor_config.json):
     "lab analyst": ["Quality", "Lab Technician"]
     "fumigation team": ["Milling", "Fumigation Team"]"

3. Review suggestions and decide:
   - Accept suggestion → Add to config file
   - Modify suggestion → Edit department/role
   - Reject → Leave as inferred

4. If accepting, update config and re-extract for 100% confidence
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
| `task_extractor.py` | `ExtractorConfig` | Configurable mappings (load from JSON or pass custom) |
| `task_extractor.py` | `DocumentContext` | Context analysis for smart mapping |
| `task_extractor.py` | `analyze_document_context()` | Detect doc type, primary dept, actors |
| `task_extractor.py` | `extract_tasks_from_text()` | Main extraction with context awareness |
| `task_extractor.py` | `preview_extraction()` | Preview tasks without saving to DB |
| `task_extractor.py` | `suggest_actor_mappings()` | Auto-suggest mappings for unmapped actors |
| `task_extractor_config.json` | JSON config | Customize actor→dept mappings |
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
