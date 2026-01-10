# Rice Export FSMS - Complete Instruction Manual

## Document Lifecycle: From Upload to Controlled Status

This manual covers the complete workflow for processing FSMS documents through gap analysis, approval, version control, and task extraction.

---

## Prerequisites

### 1. Start the FastAPI Application

```bash
uv run fastapi dev main.py --port 8000
```

Verify it's running:
```bash
curl http://localhost:8000/health
```

### 2. Ensure Folder Structure Exists

```bash
mkdir -p documents/raw documents/controlled documents/archive
```

---

## Complete Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FSMS DOCUMENT LIFECYCLE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: UPLOAD          STEP 2: ANALYZE         STEP 3: FIX GAPS           │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐           │
│  │ Place file   │   →    │ Run Gap      │   →    │ Update       │           │
│  │ in raw/      │        │ Analysis     │        │ Document     │           │
│  │ Create DB    │        │ via Skill/   │        │ Fields via   │           │
│  │ record       │        │ API/Python   │        │ API          │           │
│  └──────────────┘        └──────────────┘        └──────────────┘           │
│        │                        │                       │                    │
│        ▼                        ▼                       ▼                    │
│  Status: Draft           Gaps Identified          All Fields Complete       │
│                                                                              │
│  STEP 4: APPROVE         STEP 5: EXTRACT         STEP 6: OPERATE            │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐           │
│  │ Control      │   →    │ Extract      │   →    │ Execute      │           │
│  │ Document via │        │ Tasks from   │        │ Tasks &      │           │
│  │ doc-controller│       │ "shall"      │        │ Track        │           │
│  │ skill        │        │ statements   │        │ Completion   │           │
│  └──────────────┘        └──────────────┘        └──────────────┘           │
│        │                        │                       │                    │
│        ▼                        ▼                       ▼                    │
│  Status: Controlled      Tasks in Database       Compliance Maintained      │
│  File in controlled/                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## STEP 1: Upload Document

### 1.1 Place Physical File

Copy your document (PDF, DOCX) to the raw folder:

```bash
cp /path/to/your/Rice_Milling_SOP.pdf documents/raw/
```

### 1.2 Create Database Record

**Option A: Via API (curl)**

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "FSMS-SOP-001",
    "title": "Rice Milling Standard Operating Procedure",
    "department": "Milling",
    "version": "v0.1",
    "prepared_by": "",
    "approved_by": "",
    "record_keeper": "",
    "file_path": "documents/raw/Rice_Milling_SOP.pdf"
  }'
```

**Option B: Via Python**

```python
import requests

document = {
    "doc_id": "FSMS-SOP-001",
    "title": "Rice Milling Standard Operating Procedure",
    "department": "Milling",
    "version": "v0.1",
    "prepared_by": "",
    "approved_by": "",
    "record_keeper": "",
    "file_path": "documents/raw/Rice_Milling_SOP.pdf"
}

response = requests.post("http://localhost:8000/documents", json=document)
print(response.json())
```

**Option C: Ask Claude**

```
Claude, create a new document record for FSMS-SOP-001 titled "Rice Milling Standard Operating Procedure"
in the Milling department. The file is at documents/raw/Rice_Milling_SOP.pdf
```

---

## STEP 2: Run Gap Analysis

### 2.1 Using the iso-gap-analyzer Skill (Recommended)

**Prompt Claude:**

```
/iso-gap-analyzer FSMS-SOP-001

Analyze the document at documents/raw/Rice_Milling_SOP.pdf for ISO 22001:2018 compliance gaps.
Check all required fields and rice mill specific hazards.
```

**What Claude Will Do:**

1. Read the document using pdf/docx skill
2. Fetch document record from API
3. Check ISO 22001:2018 required fields
4. Identify rice mill hazards (Physical, Chemical, Biological)
5. Generate compliance score
6. Return gap report

### 2.2 Using gap_analyzer.py Directly

```python
from gap_analyzer import GapAnalyzer, DocumentClassifier
from pdf import extract_text  # Use pdf skill for extraction

# Extract document text
doc_text = extract_text("documents/raw/Rice_Milling_SOP.pdf")

# Classify document
classifier = DocumentClassifier()
doc_type = classifier.classify(doc_text)
print(f"Document Type: {doc_type}")

# Run gap analysis
analyzer = GapAnalyzer()
gaps = analyzer.analyze(
    doc_text=doc_text,
    doc_type=doc_type,
    doc_record={
        "doc_id": "FSMS-SOP-001",
        "prepared_by": "",
        "approved_by": "",
        "record_keeper": "",
        "department": "Milling"
    }
)

# Print gap report
print("\n=== GAP ANALYSIS REPORT ===")
print(f"Compliance Score: {gaps['score']}%")
print(f"\nMissing Fields:")
for field in gaps['missing_fields']:
    print(f"  - {field}")
print(f"\nRecommendations:")
for rec in gaps['recommendations']:
    print(f"  - {rec}")
```

### 2.3 Using API Endpoint

```bash
curl http://localhost:8000/documents/1/gap-analysis
```

### 2.4 Expected Gap Report Output

```
=== GAP ANALYSIS REPORT ===
Document: FSMS-SOP-001
Type: SOP (Standard Operating Procedure)
Compliance Score: 45%

MISSING REQUIRED FIELDS (ISO 7.5.2):
  - prepared_by: Not assigned
  - approved_by: Not assigned
  - record_keeper: Not assigned

CONTENT GAPS:
  - No critical limits defined (ISO 8.5.1.2)
  - Missing monitoring frequencies (ISO 8.5.1.3)
  - No corrective actions specified (ISO 8.5.1.4)

RICE MILL HAZARDS NOT ADDRESSED:
  - Physical: Stone, metal fragments, glass
  - Chemical: Pesticide residue, aflatoxin
  - Biological: Mold, insects, rodents

RECOMMENDATIONS:
  1. Assign document ownership (prepared_by, approved_by)
  2. Define critical limits for moisture (max 14%)
  3. Add monitoring frequency for each CCP
  4. Include corrective action procedures
  5. Address rice mill specific hazards
```

---

## STEP 3: Fix Identified Gaps

### 3.1 Update Document Record via API

**Fix ownership fields:**

```bash
curl -X PATCH http://localhost:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "prepared_by": "Quality Manager - Ahmad Khan",
    "approved_by": "Plant Director - Dr. Fatima Ali",
    "record_keeper": "Document Control - Zainab Hassan"
  }'
```

### 3.2 Ask Claude to Update

```
Claude, update document FSMS-SOP-001 with:
- prepared_by: Quality Manager - Ahmad Khan
- approved_by: Plant Director - Dr. Fatima Ali
- record_keeper: Document Control - Zainab Hassan
```

### 3.3 Update Document Content

If the document content itself needs updates (adding critical limits, monitoring frequencies, etc.):

1. Edit the physical document file
2. Replace in `documents/raw/`
3. Re-run gap analysis to verify fixes

```
Claude, re-run gap analysis on FSMS-SOP-001 to verify all gaps are fixed.
```

### 3.4 Verify All Gaps Fixed

```bash
curl http://localhost:8000/documents/1
```

Expected response shows all fields populated:
```json
{
  "id": 1,
  "doc_id": "FSMS-SOP-001",
  "title": "Rice Milling Standard Operating Procedure",
  "department": "Milling",
  "version": "v0.1",
  "status": "Draft",
  "prepared_by": "Quality Manager - Ahmad Khan",
  "approved_by": "Plant Director - Dr. Fatima Ali",
  "record_keeper": "Document Control - Zainab Hassan",
  ...
}
```

---

## STEP 4: Approve and Control Document

### 4.1 Using doc-controller Skill (Recommended)

**Prompt Claude:**

```
/doc-controller approve FSMS-SOP-001

The document has passed gap analysis. Please:
1. Verify all prerequisite fields are complete
2. Move file from raw/ to controlled/
3. Rename with version: FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf
4. Calculate SHA-256 hash for tamper detection
5. Set file to read-only
6. Update database status to Controlled
7. Log to audit trail
```

### 4.2 Using doc_controller.py Directly

```python
from doc_controller import DocumentController
import requests

# Initialize controller
controller = DocumentController(
    raw_folder="documents/raw",
    controlled_folder="documents/controlled",
    archive_folder="documents/archive"
)

# Fetch document from API
response = requests.get("http://localhost:8000/documents/1")
doc_record = response.json()

# Run prerequisite checks
checks = controller.validate_prerequisites(doc_record)
if not checks['passed']:
    print(f"Cannot approve. Missing: {checks['missing']}")
    exit(1)

# Approve document
result = controller.approve_document(
    doc_record=doc_record,
    source_file="documents/raw/Rice_Milling_SOP.pdf",
    new_version="v1.0",
    change_type="major"  # First approval is always major
)

print(f"File moved to: {result['file_path']}")
print(f"File hash: {result['file_hash']}")

# Update database via API
update_response = requests.patch(
    f"http://localhost:8000/documents/{doc_record['id']}",
    json={
        "status": "Controlled",
        "version": "v1.0",
        "approval_date": result['approval_date'],
        "file_path": result['file_path'],
        "file_hash": result['file_hash']
    }
)

print(f"Database updated: {update_response.json()}")
```

### 4.3 Using API Only

```bash
# Update status to Controlled
curl -X PATCH http://localhost:8000/documents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Controlled",
    "version": "v1.0",
    "approval_date": "2025-01-10T14:30:00Z",
    "file_path": "documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf",
    "file_hash": "a1b2c3d4e5f6..."
  }'
```

### 4.4 What Happens During Approval

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPROVAL PROCESS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. VALIDATE PREREQUISITES                                       │
│     ✓ prepared_by assigned                                       │
│     ✓ approved_by assigned                                       │
│     ✓ record_keeper assigned                                     │
│     ✓ department assigned                                        │
│     ✓ status is Draft (not Obsolete)                            │
│                                                                  │
│  2. FILE OPERATIONS                                              │
│     • Calculate SHA-256 hash of source file                     │
│     • Move: raw/SOP.pdf → controlled/FSMS-SOP-001_v1.0_SOP.pdf │
│     • Set read-only permissions (chmod 444)                     │
│                                                                  │
│  3. DATABASE UPDATE                                              │
│     • status: Draft → Controlled                                │
│     • version: v0.1 → v1.0                                      │
│     • approval_date: current timestamp                          │
│     • file_path: new controlled path                            │
│     • file_hash: SHA-256 hash                                   │
│     • version_hash: record integrity hash                       │
│                                                                  │
│  4. AUDIT TRAIL                                                  │
│     [2025-01-10T14:30:00] APPROVED | FSMS-SOP-001 | v1.0        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 Expected Output After Approval

```
✅ Document Approved Successfully!

Document: FSMS-SOP-001
Title: Rice Milling Standard Operating Procedure
Version: v0.1 → v1.0
Status: Draft → Controlled

File Operations:
  Source: documents/raw/Rice_Milling_SOP.pdf
  Destination: documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf
  Hash: a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890
  Permissions: Read-only (444)

Database Updated:
  ID: 1
  Status: Controlled
  Approval Date: 2025-01-10T14:30:00Z

Audit Log Entry Created.
```

---

## STEP 5: Extract Operational Tasks

### 5.1 Using fsms-task-extractor Skill (Recommended)

**Prompt Claude:**

```
/fsms-task-extractor FSMS-SOP-001

Extract all operational tasks from the controlled document. Parse "shall" and "must" statements,
identify actors, actions, frequencies, and critical limits. Create tasks in the database.
```

### 5.2 Using task_extractor.py Directly

```python
from task_extractor import TaskExtractor
from pdf import extract_text
import requests

# Extract document text
doc_text = extract_text("documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf")

# Initialize extractor
extractor = TaskExtractor()

# Extract tasks from text
extracted_tasks = extractor.extract_tasks(doc_text)

print(f"Found {len(extracted_tasks)} tasks")

# Prepare for API
tasks_payload = {
    "tasks": [
        {
            "document_id": 1,
            "task_description": task['full_sentence'],
            "action": task['action'],
            "object": task['object'],
            "iso_clause": task['iso_clause'],
            "critical_limit": task.get('critical_limit'),
            "frequency": task.get('frequency'),
            "assigned_department": task['department'],
            "assigned_role": task['role'],
            "priority": task['priority'],
            "source_document_version": "v1.0",
            "extracted_from_page": task.get('page', 1)
        }
        for task in extracted_tasks
    ]
}

# Create tasks via API
response = requests.post(
    "http://localhost:8000/tasks",
    json=tasks_payload
)

result = response.json()
print(f"Created {result['created_count']} tasks")
print(f"Task IDs: {result['task_ids']}")
```

### 5.3 Using API for Bulk Task Creation

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {
        "document_id": 1,
        "task_description": "The operator shall check rice moisture content every 4 hours using a calibrated moisture meter.",
        "action": "check",
        "object": "rice moisture content",
        "iso_clause": "8.5.1.3",
        "critical_limit": "14% max",
        "frequency": "Every 4 hours",
        "assigned_department": "Milling",
        "assigned_role": "Operator",
        "priority": "Critical",
        "source_document_version": "v1.0",
        "extracted_from_page": 3
      },
      {
        "document_id": 1,
        "task_description": "The quality inspector shall verify paddy intake temperature is below 35°C before processing.",
        "action": "verify",
        "object": "paddy intake temperature",
        "iso_clause": "8.5.1.2",
        "critical_limit": "<35°C",
        "frequency": "Per batch",
        "assigned_department": "Quality",
        "assigned_role": "Inspector",
        "priority": "Critical",
        "source_document_version": "v1.0",
        "extracted_from_page": 2
      }
    ]
  }'
```

### 5.4 Expected Task Extraction Output

```
=== TASK EXTRACTION REPORT ===
Document: FSMS-SOP-001 v1.0
Source: documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling_SOP.pdf

Extracted 12 tasks from 7 "shall" statements and 5 "must" statements

TASKS BY DEPARTMENT:
┌────────────┬───────┬──────────┬──────┬────────┬─────┐
│ Department │ Total │ Critical │ High │ Medium │ Low │
├────────────┼───────┼──────────┼──────┼────────┼─────┤
│ Milling    │ 6     │ 2        │ 3    │ 1      │ 0   │
│ Quality    │ 4     │ 2        │ 1    │ 1      │ 0   │
│ Storage    │ 2     │ 0        │ 1    │ 1      │ 0   │
└────────────┴───────┴──────────┴──────┴────────┴─────┘

TASKS BY ISO CLAUSE:
  • 8.5.1.2 (Critical Limits): 4 tasks
  • 8.5.1.3 (Monitoring): 5 tasks
  • 8.5.1.4 (Corrective Action): 2 tasks
  • 7.5.3 (Records): 1 task

SAMPLE EXTRACTED TASKS:
┌────┬─────────────────────────────────────────┬───────────┬──────────────┬──────────┐
│ ID │ Task Description                        │ Frequency │ Critical Lim │ Priority │
├────┼─────────────────────────────────────────┼───────────┼──────────────┼──────────┤
│ 1  │ Check rice moisture content             │ Every 4hr │ 14% max      │ Critical │
│ 2  │ Verify paddy intake temperature         │ Per batch │ <35°C        │ Critical │
│ 3  │ Inspect for foreign material            │ Per shift │ Zero defect  │ High     │
│ 4  │ Calibrate moisture meter                │ Weekly    │ ±0.5%        │ High     │
│ 5  │ Record milling parameters               │ Per batch │ -            │ Medium   │
└────┴─────────────────────────────────────────┴───────────┴──────────────┴──────────┘

All 12 tasks saved to database.
Document ID: 1
Task IDs: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
```

---

## STEP 6: Version Management (Updates)

### 6.1 Minor Update (Typo Fix, Formatting)

When a controlled document needs minor corrections:

**Prompt Claude:**

```
/doc-controller update FSMS-SOP-001 minor

The document has a typo fix. Please:
1. Increment version from v1.0 to v1.1
2. Archive old version
3. Move new file to controlled/
4. Update database
```

**What Happens:**

```
Version Change: v1.0 → v1.1 (Minor)
Old File: FSMS-SOP-001_v1.0_... → archive/FSMS-SOP-001_v1.0_ARCHIVED_20250110.pdf
New File: FSMS-SOP-001_v1.1_Rice_Milling_SOP.pdf
Tasks: Unchanged (no re-extraction needed)
```

### 6.2 Major Update (Process Change, New CCPs)

When a controlled document has substantive changes:

**Prompt Claude:**

```
/doc-controller update FSMS-SOP-001 major

The document has significant process changes. Please:
1. Increment version from v1.1 to v2.0
2. Archive old version
3. Move new file to controlled/
4. Update database
5. Re-extract tasks (process changed)
```

**What Happens:**

```
Version Change: v1.1 → v2.0 (Major)
Old File: FSMS-SOP-001_v1.1_... → archive/FSMS-SOP-001_v1.1_ARCHIVED_20250110.pdf
New File: FSMS-SOP-001_v2.0_Rice_Milling_SOP.pdf
Tasks: Old tasks marked obsolete, new tasks extracted
```

---

## Complete Prompt Examples for Claude

### Example 1: New Document - Full Workflow

```
I have uploaded a new SOP to documents/raw/Paddy_Receiving_SOP.pdf

Please:
1. Create a document record with doc_id FSMS-SOP-002, title "Paddy Receiving Procedure", department "Storage"
2. Run gap analysis using /iso-gap-analyzer
3. Tell me what fields are missing so I can provide them
```

After providing missing info:

```
Update FSMS-SOP-002 with:
- prepared_by: Storage Supervisor - Ali Raza
- approved_by: Quality Director - Dr. Hassan Malik
- record_keeper: Document Control - Ayesha Bibi

Then run gap analysis again to confirm all gaps are fixed.
```

After confirmation:

```
/doc-controller approve FSMS-SOP-002

All gaps are fixed. Please approve the document as v1.0 and move to controlled status.
```

After approval:

```
/fsms-task-extractor FSMS-SOP-002

Extract all operational tasks from the approved document and save to database.
```

### Example 2: Update Existing Document

```
I have updated the Rice Milling SOP with new critical limits for moisture content.
The updated file is at documents/raw/Rice_Milling_SOP_updated.pdf

This is a MAJOR change because critical limits changed.

Please:
1. Run gap analysis on the new version
2. If gaps are fixed, approve as v2.0 (major update)
3. Archive the old v1.0 version
4. Re-extract tasks since process changed
```

### Example 3: Quick Gap Check Only

```
/iso-gap-analyzer

Analyze documents/raw/New_Cleaning_Procedure.pdf without creating a database record.
Just tell me what ISO 22001:2018 gaps exist so I know what to fix before formal submission.
```

---

## API Quick Reference

### Documents

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Create | POST | `/documents` | `{doc_id, title, department, version, ...}` |
| List | GET | `/documents` | - |
| Get One | GET | `/documents/{id}` | - |
| Update | PATCH | `/documents/{id}` | `{status, version, ...}` |
| Delete | DELETE | `/documents/{id}` | - |
| With Tasks | GET | `/documents/{id}/tasks` | - |

### Tasks

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Bulk Create | POST | `/tasks` | `{tasks: [...]}` |
| List | GET | `/tasks` | - |
| Get One | GET | `/tasks/{id}` | - |
| Update | PATCH | `/tasks/{id}` | `{status, priority, ...}` |

### Filters

```bash
# Documents by department
GET /documents?department=Milling

# Documents by status
GET /documents?status=Controlled

# Tasks by priority
GET /tasks?priority=Critical

# Tasks by document
GET /tasks?document_id=1
```

---

## Troubleshooting

### Gap Analysis Shows Missing Fields After Update

```bash
# Verify the update was saved
curl http://localhost:8000/documents/1

# Check if field is empty string vs null
# Empty string "" still counts as missing
```

### Document Won't Approve

```
Possible causes:
1. Missing required field (prepared_by, approved_by, record_keeper)
2. Status is already Obsolete (cannot approve Obsolete documents)
3. File not found in raw/ folder

Fix: Check gap analysis report and ensure all fields are populated
```

### Tasks Not Extracting

```
Possible causes:
1. Document has no "shall" or "must" statements
2. Document is not in Controlled status
3. PDF text extraction failed

Fix:
- Verify document contains mandatory statements
- Use /pdf skill to test text extraction
- Ensure document status is Controlled before extraction
```

### Version Hash Mismatch

```
This indicates potential tampering. The stored hash doesn't match computed hash.

Check:
1. File was modified after approval
2. Database record was manually edited

Resolution: Re-approve document to regenerate hashes
```

---

## Skill Reference Card

| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `/iso-gap-analyzer {doc_id}` | Gap analysis request | Analyzes document for ISO 22001:2018 compliance |
| `/doc-controller approve {doc_id}` | Approval request | Validates, moves file, updates database |
| `/doc-controller update {doc_id} minor\|major` | Version update | Archives old, creates new version |
| `/fsms-task-extractor {doc_id}` | Task extraction | Parses "shall" statements, creates tasks |
| `/pdf {file}` | PDF reading | Extracts text from PDF documents |
| `/docx {file}` | DOCX reading | Extracts text from Word documents |
