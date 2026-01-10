---
name: doc-controller
description: Document gatekeeper implementing ISO 22001:2018 Clause 7.5.3 (Control of Documented Information). Manages document state transitions, version control, file operations, and Master Document Register. Use when approving documents, updating versions, archiving old versions, or maintaining document control. Triggers on document approval, version management, file control, or audit trail tasks.
---

# Doc Controller

Gatekeeper for Rice Export FSMS document control. Implements ISO 22001:2018 Clause 7.5.3 with version control, file operations, and Master Document Register maintenance.

## Folder Structure

```
documents/
├── raw/           # Incoming documents (Draft)
├── controlled/    # Approved documents (Master copies)
└── archive/       # Obsoleted versions (Audit trail)
```

## Versioning Rules

| Version | Meaning | Trigger |
|---------|---------|---------|
| v0.1 | Initial Draft | New document created |
| v1.0 | First Controlled | First approval |
| v1.1 | Minor Update | Typo, formatting, non-substantive |
| v2.0 | Major Update | Process, equipment, critical limits changed |

**Always ask:** "Is this a minor or major change?"

## Approval Workflow

```
1. User: "Approve document {id}"
2. Fetch document from API
3. Validate prerequisites (ownership, status)
4. If not v1.0: Ask minor/major
5. Calculate file hash (SHA-256)
6. Move file: raw → controlled
7. Rename: {DOC_ID}_{VERSION}_{TITLE}.ext
8. Set read-only permissions
9. Update database via API
10. Archive old version if exists
11. Log to audit trail
12. Return success with file location
```

## Prerequisite Checks

Before approval, verify ALL:

| Check | Field | Clause |
|-------|-------|--------|
| Ownership | prepared_by | 7.5.2 |
| Ownership | approved_by | 7.5.2 |
| Organization | department | 5.3 |
| Status | Not Obsolete | 7.5.3 |

**If ANY fails → Block and explain**

## File Naming

**Controlled format:**
```
{DOC_ID}_{VERSION}_{SANITIZED_TITLE}.{ext}
```

Examples:
- `FSMS-SOP-001_v1.0_Rice_Milling_Procedure.pdf`
- `FSMS-POL-003_v2.1_Food_Safety_Policy.docx`

**Archive format:**
```
{DOC_ID}_{VERSION}_ARCHIVED_{DATE}.{ext}
```

Example:
- `FSMS-SOP-001_v1.0_ARCHIVED_20250109.pdf`

## API Operations

**Fetch document:**
```
GET /documents/{id}
```

**Update after approval:**
```
PATCH /documents/{id}
{
  "status": "Controlled",
  "version": "v1.0",
  "approval_date": "2025-01-09T14:30:00Z",
  "file_path": "documents/controlled/...",
  "file_hash": "sha256..."
}
```

**Mark obsolete:**
```
PATCH /documents/{id}
{"status": "Obsolete"}
```

## Master Document Register

**Principle:** Only ONE version per doc_id can be "Controlled"

**Check integrity:**
```python
result = await check_master_register()
# Returns: {total_controlled, unique_documents, issues, status}
```

**Fix duplicates:**
```python
await fix_duplicate_controlled("FSMS-SOP-001")
# Keeps newest, marks others Obsolete
```

## Security Features

### File Hashing
```python
# Before moving file
file_hash = compute_file_hash(source_path)

# Store in database for tamper detection
# Later verify:
is_valid = verify_file_integrity(file_path, expected_hash)
```

### Read-Only Permissions
```python
# After moving to controlled folder
set_readonly(file_path)  # chmod 444 equivalent
```

### Audit Trail
All actions logged to `audit_log.txt`:
```
[2025-01-09T14:30:00] APPROVED | Doc: FSMS-SOP-001 | User: Plant Director | Version: v0.1 → v1.0 | File: documents/controlled/...
```

## Interactive Prompts

**Initial approval:**
```
Document FSMS-SOP-001 passed gap analysis.
Approve as v1.0? (y/n)
```

**Version update:**
```
Is this a:
1. Minor change (typo, formatting)
2. Major change (process, equipment, limits)
```

**Success:**
```
✅ Approval successful!
Document: FSMS-SOP-001
Version: v1.0
File: documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling.pdf
Hash: a1b2c3d4...
```

**Blocked:**
```
⚠️ Approval blocked!
Reason: Missing ownership fields
- prepared_by: Not set
- approved_by: Not set

Run gap analysis and assign ownership first.
```

## Error Handling

| Error | Response |
|-------|----------|
| File not in raw/ | "Source file not found in raw folder" |
| DB update fails | Rollback file move |
| Duplicate doc_id | "Document ID already exists" |
| Invalid version | "Version must match v1.0 format" |
| Obsolete document | "Cannot approve Obsolete - create new" |

## Example Usage

**User:** "Approve document 5 as controlled"

**Claude:**
1. Fetches document 5 from API
2. Validates: prepared_by ✓, approved_by ✓, department ✓
3. Current version: v0.1 (Draft)
4. New version: v1.0 (First controlled)
5. Calculates SHA-256 hash
6. Moves: `documents/raw/SOP.pdf` → `documents/controlled/FSMS-SOP-001_v1.0_Rice_Milling.pdf`
7. Sets read-only
8. Updates database: status=Controlled, version=v1.0
9. Logs: `[timestamp] APPROVED | FSMS-SOP-001 | ...`
10. Returns: "✅ Document approved as v1.0"

## References

- `references/doc_controller_template.py` - Complete implementation

When managing documents, read this reference for workflow and validation logic.
