---
name: fsms-task-extractor
description: Extracts operational tasks from controlled FSMS documents by parsing "shall" statements. Converts passive document text into active database tasks with ISO clause mapping, department assignment, and priority. Use when digitalizing SOPs, extracting compliance tasks, or populating task database from approved documents. Triggers on task extraction, document digitalization, or "shall" statement parsing.
---

# FSMS Task Extractor

Digitalizes controlled documents by extracting mandatory action statements ("shall", "must") and converting them to operational tasks in the database.

## Workflow

```
1. User: "Extract tasks from FSMS-SOP-001"
2. Verify document status = Controlled
3. Read file using pdf/docx skill
4. Scan for "shall", "must" sentences
5. Parse: actor, action, object, frequency, limits
6. Map ISO clause, department, priority
7. Check for existing tasks (duplicate prevention)
8. POST /tasks to create in database
9. Return summary report
```

## Mandatory Keywords

Extracts sentences containing (case-insensitive):
- `shall`
- `must`
- `is required to`
- `responsible for`

## Semantic Parsing

### Task Structure
```
Task = {Actor} + {Verb} + {Object} + {Condition}
```

### Parsing Example

**Input:**
```
"The operator shall check the rice moisture content every 4 hours using a calibrated moisture meter."
```

**Extracted:**
| Component | Value |
|-----------|-------|
| actor | operator |
| action | check |
| object | rice moisture content |
| frequency | Every 4 hours |
| assigned_department | Milling |
| assigned_role | Operator |

## Actor to Department Mapping

| Actor Keywords | Department | Role |
|----------------|------------|------|
| operator, miller, machine | Milling | Operator |
| inspector, QA, QC, quality | Quality | Inspector |
| packer, packaging | Packaging | Operator |
| warehouse, storage, store | Storage | Operator |
| export, shipping | Exports | Officer |
| technician, maintenance | Milling | Technician |
| manager, supervisor | Quality | Manager |

## Critical Limit Extraction

| Type | Pattern | Example |
|------|---------|---------|
| Temperature | `[<>]=?\d+°[CF]` | >60°C, <5°C |
| Percentage | `[<>]=?\d+%` | 14%, <12.5% |
| PPB/PPM | `\d+\s*ppb\|ppm` | 5 ppb, <10 ppm |
| Weight | `\d+\s*kg\|g\|mg` | 2kg, 500g |
| Time | `within\s+\d+\s*hours?` | within 2 hours |

## Frequency Extraction

| Pattern | Result |
|---------|--------|
| every X hours | Every X hours |
| per shift | Per shift |
| per batch | Per batch |
| daily | Daily |
| weekly | Weekly |
| before each X | Before each X |

## ISO Clause Auto-Mapping

| Clause | Keywords | When |
|--------|----------|------|
| 8.5.1 | control, prevent, hazard | General hazard control |
| 8.5.1.2 | limit, threshold, exceed | Has critical_limit |
| 8.5.1.3 | monitor, check, measure | Has frequency |
| 8.5.1.4 | corrective, halt, reject | Deviation actions |
| 7.5.3 | record, log, document | Record keeping |
| 7.1.5.1 | calibrate, equipment | Measurement resources |
| 9.0 | review, audit, evaluate | Performance evaluation |

## Priority Assignment

| Priority | Conditions |
|----------|------------|
| **Critical** | Has critical_limit + Clause 8.5.1.2, or "halt", "stop", "immediately" |
| **High** | Clause 8.5.1, or "before", "must", frequent monitoring |
| **Medium** | Daily/weekly tasks, "shall", "required" |
| **Low** | Monthly+, "review", "assess" |

## API Integration

### Check existing tasks:
```
GET /tasks?document_id={id}
Filter by source_document_version
```

### Create tasks:
```json
POST /tasks
{
  "tasks": [
    {
      "document_id": 5,
      "task_description": "Full sentence",
      "action": "check",
      "object": "moisture level",
      "iso_clause": "8.5.1.2",
      "critical_limit": "14% max",
      "frequency": "Every 4 hours",
      "assigned_department": "Milling",
      "assigned_role": "Operator",
      "priority": "Critical",
      "status": "Pending",
      "source_document_version": "v1.0",
      "extracted_from_page": 3
    }
  ]
}
```

## Duplicate Prevention

Before creating tasks:
1. Query existing tasks for document + version
2. If tasks exist → Skip and report count
3. If no tasks → Proceed with extraction

## Output Report Format

```
✅ Extracted 12 tasks from FSMS-SOP-001 v1.0

Tasks by Department:
- Milling: 8 tasks (3 Critical, 5 High)
- Quality: 3 tasks (2 High, 1 Medium)
- Management: 1 task (1 Medium)

Priority Breakdown:
- Critical: 3 tasks
- High: 7 tasks
- Medium: 2 tasks

All tasks saved to database. Document ID: 5
```

## Prerequisites

- Document must have status = "Controlled"
- File must exist in `documents/controlled/`
- Use pdf/docx skill for text extraction first

## Example Usage

**User:** "Extract tasks from the Rice Milling SOP"

**Claude:**
1. Finds FSMS-SOP-001 via API
2. Verifies status = Controlled
3. Reads `documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling.pdf`
4. Extracts text using pdf skill
5. Finds 12 "shall" statements
6. Parses each into task components
7. Creates 12 tasks via POST /tasks
8. Returns summary report

## References

- `references/task_extractor_template.py` - Complete implementation

When extracting tasks, read this reference for parsing logic and API integration.
