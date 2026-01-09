# Complete Skills Architecture & Implementation Guide

## Project: Rice Export FSMS - ISO 22001:2018 Compliance System

**Document Version:** 2.0  
**Created:** January 2026  
**Purpose:** Master reference for all 6 skills, dependencies, and implementation sequence

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Skill Architecture](#skill-architecture)
3. [Detailed Skill Descriptions](#detailed-skill-descriptions)
4. [Dependency Matrix](#dependency-matrix)
5. [Implementation Checklist](#implementation-checklist)
6. [Execution Sequence](#execution-sequence)

---

## System Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│  TIER 1: META LAYER                             │
│  skill-creator (from Panaversity)               │
│  ↓ Generates all custom skills                  │
├─────────────────────────────────────────────────┤
│  TIER 2: TECHNICAL LAYER (Infrastructure)       │
│  1. sqlmodel-architect                          │
│  2. fastapi-route-wizard                        │
│  3. pytest-inspector                            │
├─────────────────────────────────────────────────┤
│  TIER 3: BASE SKILLS (from Panaversity)         │
│  pdf, docx, xlsx                                │
├─────────────────────────────────────────────────┤
│  TIER 4: WORKFLOW LAYER (Business Logic)        │
│  4. iso-gap-analyzer                            │
│  5. doc-controller                              │
│  6. fsms-task-extractor                         │
└─────────────────────────────────────────────────┘
```

### Core Principles

1. **Waterfall + Feedback Loop**: Technical skills first, then workflow skills
2. **ISO 22001 Compliance**: Every skill maps to specific clauses
3. **Traceability**: Every task links back to source document
4. **Audit Readiness**: All changes logged with timestamp and owner

---

## Skill Architecture

### ISO 22001 Clause Mapping

| Skill | Primary Output | ISO Clause | Layer |
|-------|---------------|------------|-------|
| sqlmodel-architect | Database Schema | Infrastructure | Technical |
| fastapi-route-wizard | REST API | Infrastructure | Technical |
| pytest-inspector | Test Suite | Clause 9.0 (Performance) | Technical |
| iso-gap-analyzer | Gap Report | Clause 4.0 & 8.0 | Workflow |
| doc-controller | Controlled File | Clause 7.5 (Doc Control) | Workflow |
| fsms-task-extractor | Task Records | Clause 8.5 (Operations) | Workflow |

---

## Detailed Skill Descriptions

---

## SKILL 1: sqlmodel-architect

### Classification
- **Type:** Technical Infrastructure
- **Layer:** Tier 2 (Foundation)
- **Priority:** FIRST skill to generate
- **Dependencies:** None

### Purpose
The "Data Designer" - Creates the database schema and manages connection to Neon Postgres. Sets the "rules" for all data in the system with ISO 22001 traceability built-in.

### Key Features

1. **Parent-Child Relationship Design**
   - Document (1) → Tasks (N)
   - Cascade delete handling
   - Foreign key integrity

2. **Audit-Ready Shadow Fields**
   - `created_at`: Record creation timestamp
   - `updated_at`: Auto-update on modification
   - `version_hash`: SHA-256 for tamper detection

3. **Neon Cloud Integration**
   - Connection pooling
   - Retry logic for network issues
   - Auto-create tables
   - Session lifecycle management

### Database Schema

#### Document Table Fields
```
- id: Primary Key (auto-increment)
- doc_id: Unique identifier (e.g., "FSMS-SOP-001")
- title: Document title
- department: "Milling", "Quality", "Exports", etc.
- version: Format "v1.0", "v1.1", "v2.0"
- status: "Draft", "Controlled", "Obsolete"
- prepared_by: Author name
- approved_by: Approver name
- record_keeper: Responsible person
- approval_date: When approved
- review_cycle_months: Default 12
- iso_clauses: JSON array of applicable clauses
- file_path: Location of controlled file
- file_hash: SHA-256 of file content
- created_at, updated_at, version_hash: Audit fields
```

#### Task Table Fields
```
- id: Primary Key
- document_id: Foreign Key → Document.id (CASCADE)
- task_description: Full "shall" statement
- action: Verb (e.g., "check", "inspect")
- object: Target (e.g., "moisture level")
- iso_clause: REQUIRED field (e.g., "8.5.1.2")
- critical_limit: e.g., "14% max", ">60°C"
- frequency: e.g., "Every 4 hours"
- assigned_department: Department responsible
- assigned_role: e.g., "Shift Supervisor"
- priority: "Critical", "High", "Medium", "Low"
- status: "Pending", "Completed", "Overdue"
- source_document_version: Version lock
- extracted_from_page: Source page number
- created_at: Creation timestamp
```

### Technical Requirements

```bash
# UV Dependencies
uv add sqlmodel psycopg2-binary python-dotenv

# Environment Variables (.env)
DATABASE_URL=postgresql://user:pass@ep-xxxxx.aws.neon.tech/fsms_db
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

### Generation Prompt

```
Claude, use the skill-creator skill to generate sqlmodel-architect.

Requirements:

1. FRAMEWORK:
   - SQLModel (combines SQLAlchemy + Pydantic)
   - Target: Neon Postgres cloud database
   - Load DATABASE_URL from .env via python-dotenv

2. DOCUMENT MODEL:
   Create table with fields: id, doc_id (unique), title, department, 
   version (regex: v\d+\.\d+), status (enum), prepared_by, approved_by, 
   record_keeper, approval_date, review_cycle_months (default 12), 
   iso_clauses, file_path, file_hash, created_at, updated_at, version_hash
   
   Departments: "Milling", "Quality", "Exports", "Packaging", "Storage"
   Status: "Draft", "Controlled", "Obsolete"

3. TASK MODEL:
   Create table with fields: id, document_id (FK with CASCADE), 
   task_description, action, object, iso_clause (REQUIRED), 
   critical_limit, frequency, assigned_department, assigned_role, 
   priority (enum), status (enum), source_document_version, 
   extracted_from_page, created_at
   
   Priority: "Critical", "High", "Medium", "Low"
   Status: "Pending", "Completed", "Overdue"

4. DATABASE CONNECTION (database.py):
   - Engine with connection pooling (pool_size=5, max_overflow=10)
   - Session factory with context manager
   - Retry logic (max 3 retries, exponential backoff)
   - Auto-create tables function
   - Health check function

5. VALIDATION RULES:
   - task.iso_clause cannot be NULL (CHECK constraint)
   - document.version must match v\d+\.\d+ pattern
   - Status transitions: Draft → Controlled → Obsolete (one-way)

Output files: models.py, database.py
Output folder: .claude/skills/sqlmodel-architect/
```

### Expected Outputs
- **models.py** (200-300 lines): Document/Task classes, enums, validation
- **database.py** (100-150 lines): Engine, SessionLocal, health check

### Verification
```bash
uv run python -c "from database import create_tables; create_tables(); print('✅ Success')"
```

---

## SKILL 2: fastapi-route-wizard

### Classification
- **Type:** Technical Infrastructure
- **Layer:** Tier 2 (Foundation)
- **Priority:** SECOND skill
- **Dependencies:** sqlmodel-architect (needs models.py)

### Purpose
The "API Builder" - Creates REST API for database operations. Translates HTTP requests into database actions with ISO validation.

### Key Features

1. **Automatic CRUD Generation**
   - CREATE: POST endpoints
   - READ: GET with filters
   - UPDATE: PATCH endpoints
   - DELETE: Soft delete (status="Obsolete")

2. **ISO-Specific Validation**
   - Ownership fields required (prepared_by, approved_by)
   - Status transitions enforced
   - Version format validated

3. **Department Filtering**
   - GET /tasks?department=Milling
   - GET /documents?status=Controlled&department=Quality

4. **Relationship Handling**
   - GET /documents/{id}/tasks (nested response)
   - Eager loading for performance

### API Endpoints

#### Documents
```
POST /documents          Create new document
GET /documents           List all (filters: department, status, version)
GET /documents/{id}      Get single document
PATCH /documents/{id}    Update status/version
DELETE /documents/{id}   Soft delete (mark Obsolete)
GET /documents/{id}/tasks Get document with tasks
```

#### Tasks
```
POST /tasks             Bulk create tasks (array)
GET /tasks              List (filters: department, status, priority, iso_clause)
PATCH /tasks/{id}       Update status/priority
```

#### System
```
GET /health             Database connection status
GET /audit-trail/{id}   Document change history
```

### Technical Requirements

```bash
# UV Dependencies
uv add fastapi uvicorn pydantic python-multipart
```

### Generation Prompt

```
Claude, use skill-creator to generate fastapi-route-wizard.

Requirements:

1. FRAMEWORK:
   - FastAPI with SQLModel integration
   - Uvicorn ASGI server
   - Automatic OpenAPI docs at /docs

2. DEPENDENCY:
   - Import models from models.py
   - Import database session from database.py

3. DOCUMENT ENDPOINTS:
   POST /documents: Validate doc_id unique, version format, ownership fields
   GET /documents: Filters (department, status, version), pagination
   GET /documents/{id}: Single document or 404
   PATCH /documents/{id}: Update status/version/approval_date
   DELETE /documents/{id}: Soft delete (status="Obsolete")
   GET /documents/{id}/tasks: Nested response with tasks

4. TASK ENDPOINTS:
   POST /tasks: Bulk create (array), validate document_id exists
   GET /tasks: Filters (document_id, department, status, priority)
   PATCH /tasks/{id}: Update status, priority

5. VALIDATION:
   - Ownership fields required on POST/PATCH
   - Version format: v\d+\.\d+
   - Status transitions: Draft → Controlled → Obsolete
   - Task iso_clause cannot be empty

6. ERROR HANDLING:
   - 400: Validation errors (detailed message)
   - 404: Resource not found
   - 500: Database errors
   - Include error_code field

7. CORS:
   - Allow origins: ["*"] (development)
   - Methods: GET, POST, PATCH, DELETE

Output file: main.py
Output folder: .claude/skills/fastapi-route-wizard/
```

### Expected Output
- **main.py** (400-600 lines): FastAPI app, all endpoints, error handlers

### Verification
```bash
uv run uvicorn main:app --reload
# Open http://localhost:8000/docs
# Verify Swagger UI shows all endpoints
```

---

## SKILL 3: pytest-inspector

### Classification
- **Type:** Technical Infrastructure
- **Layer:** Tier 2 (Foundation)
- **Priority:** THIRD skill
- **Dependencies:** fastapi-route-wizard (needs main.py)

### Purpose
The "Quality Assurance" - Automated testing for ISO compliance logic. Proves system works via TDD.

### Key Features

1. **API Testing**: All endpoints validated
2. **ISO Compliance**: Ownership, status transitions, version format
3. **Integrity**: Document-Task relationships, cascade deletes

### Test Categories

**Unit Tests (test_models.py)**
- Document model validation
- Task requires iso_clause
- Version format validation
- Status enum validation

**Integration Tests (test_api.py)**
- Create/read/update documents
- Status transition rules
- Bulk task creation
- Filter queries

**E2E Tests (test_workflow.py)**
- Full document lifecycle (Draft → Controlled → Tasks)
- Document deletion cascades to tasks
- Duplicate prevention

### Technical Requirements

```bash
# UV Dependencies
uv add pytest pytest-asyncio httpx

# Environment
DATABASE_URL_TEST=postgresql://user:pass@ep-xxx.neon.tech/fsms_test
```

### Generation Prompt

```
Claude, use skill-creator to generate pytest-inspector.

Requirements:

1. FRAMEWORK:
   - pytest with async support
   - httpx for API testing
   - Separate test database

2. TEST STRUCTURE:
   tests/
   ├── conftest.py (fixtures: test_db, test_client, sample data)
   ├── test_models.py (unit tests for models)
   ├── test_api.py (integration tests for endpoints)
   └── test_workflow.py (E2E tests)

3. UNIT TESTS:
   - test_document_requires_ownership_fields
   - test_task_requires_iso_clause
   - test_version_format_validation
   - test_status_enum_validation

4. INTEGRATION TESTS:
   Documents: create, get, filter, update, delete
   Tasks: bulk create, filter, update
   Validation: missing fields, invalid status transitions

5. E2E TESTS:
   - test_full_document_lifecycle
   - test_document_deletion_cascades
   - test_duplicate_prevention

6. COVERAGE:
   - Aim for 80%+ coverage
   - Generate HTML report: pytest --cov --cov-report=html

Output folder: .claude/skills/pytest-inspector/
```

### Expected Output
- **tests/** directory with conftest.py, test_*.py files

### Verification
```bash
uv run pytest -v
# Expected: 25+ passed tests
```

---

## SKILL 4: iso-gap-analyzer

### Classification
- **Type:** Workflow/Business Logic
- **Layer:** Tier 4 (Brain)
- **Priority:** FOURTH skill (first workflow skill)
- **Dependencies:** pdf, docx (base skills), fastapi-route-wizard

### Purpose
The "Auditor" - First quality gate. Classifies documents, audits against ISO 22001, produces Gap Reports.

### Key Features

1. **Document Classification**
   - Policy: High-level commitment (Clause 5.2)
   - SOP: Operational procedure (Clause 8.1)
   - Process Flow: Detailed diagram
   - Record: Evidence template

2. **Compliance Scoring**
   ```
   Score = (Present Clauses / Required Clauses) × 100
   ```
   Blocks if < 100%

3. **Rice-Specific Hazards**
   - Physical: Stones, metal, husks
   - Chemical: Pesticides, aflatoxin
   - Biological: Mold, moisture

4. **Ownership Verification**
   - Prepared By required
   - Approved By required
   - Department assigned

### ISO 22001 Checklist

**SOP Requirements:**
- Prepared By / Approved By fields (Clause 7.5.2)
- Process description (Clause 8.1)
- Hazard controls (Clause 8.5.1)
- Critical limits (Clause 8.5.1.2)
- Monitoring frequency (Clause 8.5.1.3)
- Corrective actions (Clause 8.5.1.4)

**Policy Requirements:**
- Food safety commitment (Clause 5.2.1)
- Regulatory compliance (Clause 5.2.2)
- Roles/responsibilities (Clause 5.3)
- Document control metadata (Clause 7.5.2)

### Technical Requirements

```bash
# UV Dependencies
uv add PyPDF2 python-docx httpx

# Base Skills (must exist)
.claude/skills/pdf/
.claude/skills/docx/
```

### Generation Prompt

```
Claude, use skill-creator to generate iso-gap-analyzer.

Requirements:

1. FRAMEWORK KNOWLEDGE:
   Embed ISO 22001:2018 awareness:
   - Clause 5: Leadership (5.2 Policy, 5.3 Roles)
   - Clause 7: Support (7.5.2 Creating docs, 7.5.3 Control)
   - Clause 8: Operation (8.1 Planning, 8.5.1 Hazard control)

2. TOOL INTEGRATION:
   - Use pdf skill for PDF extraction
   - Use docx skill for Word extraction
   - Scan /documents/raw/ folder

3. CLASSIFICATION LOGIC:
   Detect document type by keywords:
   - Policy: "policy", "commitment", "management"
   - SOP: "procedure", "shall", "step", "instruction"
   - Process Flow: "input", "output", "decision"
   - Record: "date", "time", "checked by"

4. GAP ANALYSIS:
   For SOPs check:
   - Prepared By / Approved By fields
   - Department specified
   - Hazard identification
   - Critical limits (if HACCP)
   - Monitoring frequency
   - Corrective actions
   
   Rice Mill Specific:
   - Moisture control mentioned
   - Metal detection mentioned
   - Aflatoxin testing mentioned
   - Pest control mentioned

5. GAP REPORT FORMAT:
   Generate markdown with:
   - Compliance score (%)
   - Present elements (✅)
   - Missing elements (❌) with severity
   - Recommendations with specific text suggestions
   - ISO clause references

6. INTERACTIVE MODE:
   After report: "Would you like me to add suggested text?"
   If accepted → Update document

7. API INTEGRATION:
   If user accepts report:
   - POST /documents (create Draft record)
   - Include: doc_id, title, department, prepared_by, status="Draft"

Output folder: .claude/skills/iso-gap-analyzer/
```

### Expected Behavior
```
User: "Analyze new Milling SOP"
→ Reads file (pdf skill)
→ Classifies as "SOP"
→ Checks 12 requirements
→ Finds 3 gaps
→ Generates report
→ Asks accept/reject
→ Creates Draft in database
```

---

## SKILL 5: doc-controller

### Classification
- **Type:** Workflow/Business Logic
- **Layer:** Tier 4 (Brain)
- **Priority:** FIFTH skill
- **Dependencies:** iso-gap-analyzer, fastapi-route-wizard

### Purpose
The "Gatekeeper" - Manages state transitions, version control, physical file operations. Implements ISO Clause 7.5.3.

### Key Features

1. **Version Cascading**
   ```
   v0.1 (Draft) → v1.0 (First Approval)
                ↓
   v1.1 (Minor) or v2.0 (Major)
   ```
   - Minor: Typos, formatting
   - Major: Process changes, new equipment

2. **Approval Gate**
   ```
   Approval = (Gap_Free == True) ∧ (Owner_Assigned == True)
   ```

3. **Physical & Digital Sync**
   - Move: /raw → /controlled
   - Rename: FSMS-SOP-001_v1.0_Title.pdf
   - Database: status="Controlled", approval_date set

4. **Master Document Register**
   - Only ONE current version
   - Old versions → /archive
   - Database marked "Obsolete"

### File Naming Convention
```
[DOC_ID]_[VERSION]_[SANITIZED_TITLE].[ext]

Examples:
FSMS-SOP-001_v1.0_Rice_Milling_Procedure.pdf
FSMS-POL-003_v2.1_Food_Safety_Policy.docx
```

### Technical Requirements

```bash
# UV Dependencies
uv add httpx

# Standard library: shutil, os, datetime, hashlib
```

### Generation Prompt

```
Claude, use skill-creator to generate doc-controller.

Requirements:

1. FRAMEWORK:
   ISO 22000:2018 Clauses 7.5.2, 7.5.3 (Document Control)

2. VERSIONING:
   Semantic: v{major}.{minor}
   - Drafts: v0.1
   - First approval: v1.0
   - Minor changes: +0.1
   - Major changes: +1.0
   Ask user: "Minor or major change?"

3. APPROVAL GATE:
   Verify before moving:
   - GET /documents/{id} → gap_report compliance_score == 100
   - prepared_by not empty
   - approved_by not empty
   - department specified
   If fail: Log error, refuse, return message

4. FILE OPERATIONS:
   Move: /documents/raw/{file} → /documents/controlled/{doc_id}_v{ver}_{title}.{ext}
   Sanitize title (remove spaces, special chars)
   Set read-only permissions
   Archive old versions: /documents/archive/

5. DATABASE OPERATIONS:
   PATCH /documents/{id}
   - status="Controlled"
   - version="v1.0"
   - approval_date=now
   - file_path, file_hash
   - review_cycle_months=12
   
   If new version:
   - Mark old as "Obsolete"
   - Set replaced_by_id

6. MASTER DOCUMENT REGISTER:
   - Query: GET /documents?status=Controlled
   - Ensure no duplicate doc_ids
   - Mark older as Obsolete if duplicate

7. SECURITY:
   - Hash file content (SHA-256)
   - Store hash in database
   - Verify on access (tamper detection)
   - Log to audit_log.txt

Output folder: .claude/skills/doc-controller/
```

### Expected Behavior
```
User: "Approve document 5 as v1.0"
→ Checks gap_report (100%)
→ Verifies ownership
→ Moves file to /controlled
→ Renames: FSMS-SOP-001_v1.0_Milling.pdf
→ Sets read-only
→ Updates DB: status="Controlled"
→ Returns: "✅ Approved. Location: ..."
```

---

## SKILL 6: fsms-task-extractor

### Classification
- **Type:** Workflow/Business Logic
- **Layer:** Tier 4 (Brain)
- **Priority:** SIXTH skill
- **Dependencies:** doc-controller, pdf, docx, fastapi-route-wizard

### Purpose
The "Digitalizer" - Converts passive text into active tasks. Scans for "shall" statements, creates task records.

### Key Features

1. **Linguistic Pattern Matching**
   - Keywords: "shall", "must", "is required to", "responsible for"
   - Extracts full sentences

2. **Semantic Segmentation**
   ```
   Task = {Actor} + {Verb(Shall)} + {Object} + {Condition}
   
   "Miller shall inspect sifter before each shift"
   → Actor: Miller
   → Verb: inspect
   → Object: sifter
   → Condition: before each shift
   ```

3. **Critical Limit Extraction**
   - Temperature: >60°C, <5°C
   - Moisture: 14%, <14%
   - Time: 4 hours, within 2 hours
   - Weight: >2kg, 500g max
   - PPB: <5 ppb aflatoxin

4. **ISO Clause Mapping**
   ```
   "Check moisture" → 8.5.1.2 (Critical Limits)
   "Calibrate equipment" → 7.1.5.1 (Measurement)
   "Record in log" → 7.5.3 (Documentation)
   "Corrective action" → 8.5.1.4 (Actions)
   ```

5. **Department Assignment**
   ```
   "Miller" → Milling
   "Quality Lab" → Quality
   "Supervisor" → Management
   ```

6. **Traceability**
   - document_id
   - source_document_version
   - extracted_from_page

### Extraction Example

**Input Text:**
```
"The milling operator shall check the rice moisture content every 
4 hours using a calibrated digital moisture meter. The moisture 
content must not exceed 14%."
```

**Extracted Tasks:**
```json
[
  {
    "task_description": "Check rice moisture content every 4 hours",
    "action": "check",
    "object": "rice moisture content",
    "iso_clause": "8.5.1.2",
    "critical_limit": "14% max",
    "frequency": "Every 4 hours",
    "assigned_department": "Milling",
    "assigned_role": "Operator",
    "priority": "Critical"
  }
]
```

### Technical Requirements

```bash
# UV Dependencies
uv add httpx

# Standard library: re, json
# Base skills: pdf, docx
```

### Generation Prompt

```
Claude, use skill-creator to generate fsms-task-extractor.

Requirements:

1. PARSING ENGINE:
   - Use pdf skill for PDFs
   - Use docx skill for Word
   - Scan /documents/controlled/ only

2. MANDATORY ACTION DETECTION:
   Regex patterns for:
   - "shall" (case-insensitive)
   - "must"
   - "is required to"
   - "responsible for"
   Extract full sentence (capital → period)

3. SEMANTIC PARSING:
   Extract for each sentence:
   - Actor: Noun before "shall"
   - Action: Verb after "shall"
   - Object: Noun phrase after verb
   - Condition: Frequency indicators

4. CRITICAL LIMIT EXTRACTION:
   Regex for thresholds:
   - Temperature: ([<>]=?\s*\d+\s*°?[CF])
   - Percentage: ([<>]=?\s*\d+(\.\d+)?%)
   - Time: (\d+\s*(hours?|minutes?))
   - Weight: (\d+(\.\d+)?\s*(kg|g))
   - PPB: (\d+\s*ppb|ppm)

5. FREQUENCY EXTRACTION:
   - "every X hours" → "Every X hours"
   - "per shift" → "Per shift"
   - "daily" → "Daily"

6. ISO CLAUSE MAPPING:
   Auto-assign by keywords:
   - 8.5.1: "control", "prevent", "hazard"
   - 8.5.1.2: "limit", "exceed", + has critical_limit
   - 8.5.1.3: "monitor", "check", + has frequency
   - 8.5.1.4: "corrective", "halt", "notify"
   - 7.5.3: "record", "log", "document"

7. DEPARTMENT/ROLE:
   Map actors:
   - "miller", "operator" → Milling
   - "inspector", "QA" → Quality
   - "technician" → Maintenance
   - "manager", "supervisor" → Management

8. PRIORITY:
   - Critical: has critical_limit AND Clause 8.5.1.2
   - High: Clause 8.5.1, frequency ≤ per shift
   - Medium: Clause 7.5.3, daily/weekly
   - Low: Clause 9.0, monthly+

9. API INTEGRATION:
   POST /tasks (bulk)
   - Array of tasks
   - Link to document_id
   - Include source_document_version
   - Include extracted_from_page

10. DUPLICATE PREVENTION:
    Before creating:
    - GET /tasks?document_id={id}&source_document_version={ver}
    - If exists, skip
    - Return: "Tasks already extracted for this version"

Output folder: .claude/skills/fsms-task-extractor/
```

### Expected Behavior
```
User: "Extract tasks from FSMS-SOP-001"
→ Verifies status="Controlled"
→ Reads file
→ Scans for "shall", "must"
→ Extracts 12 tasks
→ Parses: actor, action, limit, frequency
→ Assigns ISO clauses, departments
→ Sets priorities
→ POSTs to /tasks
→ Returns: "✅ Extracted 12 tasks"
```

---

## Dependency Matrix

### Visual Flow

```
skill-creator (Panaversity Base)
    │
    ├──> sqlmodel-architect
    │       └──> models.py, database.py
    │               │
    ├──> fastapi-route-wizard (needs models.py)
    │       └──> main.py
    │               │
    ├──> pytest-inspector (needs main.py)
    │       └──> tests/
    │
    ├──> iso-gap-analyzer (needs pdf, docx, main.py)
    │       └──> Gap reports → Draft in DB
    │               │
    ├──> doc-controller (needs gap reports, main.py)
    │       └──> Controlled files → Controlled in DB
    │               │
    └──> fsms-task-extractor (needs controlled files, pdf, docx, main.py)
            └──> Task records in DB
```

### Dependency Table

| Skill | Depends On | Generates | Used By |
|-------|-----------|-----------|---------|
| skill-creator | - | All 6 skills | - |
| pdf, docx | - (Panaversity) | - | iso-gap-analyzer, fsms-task-extractor |
| sqlmodel-architect | skill-creator | models.py, database.py | fastapi-route-wizard |
| fastapi-route-wizard | sqlmodel-architect | main.py | All workflow skills, pytest-inspector |
| pytest-inspector | fastapi-route-wizard | tests/ | - |
| iso-gap-analyzer | pdf, docx, fastapi-route-wizard | Gap reports, Draft DB | doc-controller |
| doc-controller | iso-gap-analyzer, fastapi-route-wizard | Controlled files | fsms-task-extractor |
| fsms-task-extractor | doc-controller, pdf, docx, fastapi-route-wizard | Task records | - |

---

## Implementation Checklist

### Phase 1: Environment Setup (5 min)

```bash
# 1. Create project
[ ] mkdir rice-export-fsms && cd rice-export-fsms
[ ] mkdir -p documents/{raw,controlled,archive}
[ ] mkdir -p .claude/skills

# 2. Initialize UV
[ ] uv init
[ ] uv venv
[ ] source .venv/bin/activate  # or .venv\Scripts\activate (Windows)

# 3. Environment file
[ ] Create .env with DATABASE_URL and DATABASE_URL_TEST

# 4. Git
[ ] git init
[ ] Add .gitignore: .env, .venv/, documents/
[ ] git commit -m "Initial structure"

# 5. Clone base skills
[ ] Clone Panaversity repo temporarily
[ ] Copy skill-creator, pdf, docx to .claude/skills/
[ ] Remove temp clone
[ ] Verify: ls .claude/skills/ shows 3 folders
```

### Phase 2: Technical Layer (20 min)

#### Step 1-2: sqlmodel-architect
```bash
[ ] Generate: "Use skill-creator to generate sqlmodel-architect"
[ ] Verify: .claude/skills/sqlmodel-architect/SKILL.md exists
[ ] Create: "Use sqlmodel-architect to create models.py and database.py"
[ ] Install: uv add sqlmodel psycopg2-binary python-dotenv
[ ] Test: uv run python -c "from database import create_tables; create_tables()"
[ ] Verify: Check Neon console for tables
```

#### Step 3-4: fastapi-route-wizard
```bash
[ ] Generate: "Use skill-creator to generate fastapi-route-wizard"
[ ] Verify: .claude/skills/fastapi-route-wizard/SKILL.md exists
[ ] Create: "Use fastapi-route-wizard to create main.py"
[ ] Install: uv add fastapi uvicorn pydantic python-multipart
[ ] Test: uv run uvicorn main:app --reload
[ ] Verify: Open http://localhost:8000/docs
[ ] Test: POST /documents with sample data
[ ] Verify: Check Neon for record
```

#### Step 5-6: pytest-inspector
```bash
[ ] Generate: "Use skill-creator to generate pytest-inspector"
[ ] Create: "Use pytest-inspector to create test suite"
[ ] Install: uv add pytest pytest-asyncio httpx
[ ] Verify: tests/ directory with test files
[ ] Test: uv run pytest -v
[ ] Verify: All tests pass (green)
```

### Phase 3: Workflow Layer (15 min)

```bash
[ ] Generate iso-gap-analyzer
[ ] Install: uv add PyPDF2 python-docx
[ ] Verify: .claude/skills/iso-gap-analyzer/

[ ] Generate doc-controller
[ ] Install: uv add httpx (if not already)
[ ] Verify: .claude/skills/doc-controller/

[ ] Generate fsms-task-extractor
[ ] Verify: .claude/skills/fsms-task-extractor/
```

### Phase 4: End-to-End Test (15 min)

```bash
# 1. Prepare test document
[ ] Create simple SOP with "shall" statements
[ ] Save to documents/raw/test_sop.pdf

# 2. Analyze
[ ] "Analyze test SOP in raw folder"
[ ] Verify gap report
[ ] Accept report
[ ] Check Neon: Draft record exists

# 3. Approve
[ ] "Approve document 1 as v1.0"
[ ] Verify file moved to /controlled
[ ] Verify renamed: FSMS-SOP-001_v1.0_*.pdf
[ ] Check Neon: status="Controlled"

# 4. Extract tasks
[ ] "Extract tasks from document 1"
[ ] Verify console shows task count
[ ] Check Neon: SELECT * FROM tasks WHERE document_id=1
[ ] Verify tasks have iso_clause, department, priority

# 5. Query
[ ] "Show Critical tasks for Milling"
[ ] Verify filtered list returned
```

### Phase 5: Production (Optional)

```bash
[ ] Create README.md
[ ] Document API beyond Swagger
[ ] User manual from template
[ ] Review .gitignore
[ ] Set up Neon backups
[ ] Run: uv run pytest --cov --cov-report=html
[ ] Aim for 80%+ coverage
```

---

## Execution Sequence

### Critical Path (Must Follow Order)

```
1. Environment Setup (5 min)
   ↓
2. Generate sqlmodel-architect (2 min)
   ↓
3. Run sqlmodel-architect → Create models.py, database.py (3 min)
   ↓
4. Generate fastapi-route-wizard (2 min)
   ↓
5. Run fastapi-route-wizard → Create main.py (3 min)
   ↓
6. Generate pytest-inspector (2 min)
   ↓
7. Run pytest-inspector → Create tests (5 min)
   ↓
8. Generate iso-gap-analyzer (2 min)
   ↓
9. Generate doc-controller (2 min)
   ↓
10. Generate fsms-task-extractor (2 min)
   ↓
11. End-to-End Test (15 min)
```

### Time Budget

| Phase | Duration |
|-------|----------|
| Environment | 5 min |
| sqlmodel-architect | 5 min |
| fastapi-route-wizard | 5 min |
| pytest-inspector | 7 min |
| Workflow skills (3) | 6 min |
| E2E testing | 15 min |
| **TOTAL** | **~45 min** |

---

## Summary

### Deliverables

✅ **6 Production Skills:**
1. sqlmodel-architect (Database)
2. fastapi-route-wizard (API)
3. pytest-inspector (Testing)
4. iso-gap-analyzer (Audit)
5. doc-controller (Control)
6. fsms-task-extractor (Tasks)

✅ **Key Features:**
- ISO 22001 compliance
- Neon Postgres integration
- REST API with Swagger docs
- Automated testing (80%+ coverage)
- Complete audit trail
- Rice mill-specific hazard recognition

✅ **Architecture:**
- 4-tier layered design
- Clear dependencies
- Modular and scalable
- Production-ready

### Next Step

```bash
mkdir rice-export-fsms && cd rice-export-fsms
uv init
```

Then ask Claude:
> "Let's start by generating the sqlmodel-architect skill"

---

**END OF DOCUMENT**

*This is your master reference for the complete Rice Export FSMS system implementation.*
