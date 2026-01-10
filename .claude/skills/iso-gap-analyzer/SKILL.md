---
name: iso-gap-analyzer
description: ISO 22001:2018 gap analysis for Rice Export FSMS documents. Classifies documents (Policy/SOP/Process Flow/Record), audits against ISO clauses, checks rice mill hazards, generates compliance reports with scores. Use when analyzing new documents, checking ISO compliance, performing gap analysis, or preparing documents for FSMS registration. Triggers on document review, compliance audit, or quality gate tasks.
---

# ISO Gap Analyzer

First quality gate for Rice Export FSMS. Classifies documents, audits against ISO 22001:2018, identifies gaps, and creates Draft records when compliant.

## Workflow

```
1. Scan documents/raw/ folder
2. Extract text (use pdf/docx skills)
3. Classify document type
4. Check required elements
5. Generate gap report
6. If 100%: Offer to create Draft
7. If <100%: List specific fixes
```

## Document Classification

| Type | Keywords | Indicators |
|------|----------|------------|
| **POLICY** | policy, commitment, management | High-level, 2-5 pages, no steps |
| **SOP** | procedure, shall, step, instruction | Numbered steps, action verbs |
| **PROCESS_FLOW** | input, output, decision | Diagrams, flowcharts |
| **RECORD** | date, checked by, signature | Tables, checkboxes, forms |

## ISO 22001:2018 Clauses Checked

### Leadership (Clause 5)
- 5.2: Food safety policy
- 5.3: Roles and responsibilities

### Support (Clause 7)
- 7.5.2: Creating documented information (Prepared By, Approved By)
- 7.5.3: Document control (version, dates, retention)

### Operation (Clause 8)
- 8.1: Operational planning
- 8.5.1: Hazard control (HACCP)
- 8.5.1.2: Critical limits
- 8.5.1.3: Monitoring system
- 8.5.1.4: Corrective actions

## Required Elements by Document Type

### SOP Requirements
| Element | Clause | Severity |
|---------|--------|----------|
| Prepared By | 7.5.2 | Critical |
| Approved By | 7.5.2 | Critical |
| Department | 5.3 | Critical |
| Hazard identification | 8.5.1 | Critical |
| Critical limits | 8.5.1.2 | High |
| Monitoring frequency | 8.5.1.3 | High |
| Corrective actions | 8.5.1.4 | High |

### Policy Requirements
| Element | Clause | Severity |
|---------|--------|----------|
| Food safety commitment | 5.2.1 | Critical |
| Regulatory compliance | 5.2.2 | Critical |
| Roles defined | 5.3 | High |
| Document control | 7.5.2 | High |

## Rice Mill Specific Hazards

### Physical Hazards
- **Check for:** stone, metal, glass, foreign object
- **Controls:** magnetic separator, destoner, sifter, metal detector
- **Limits:** Metal <2mm, Stone zero tolerance

### Chemical Hazards
- **Check for:** aflatoxin, pesticide, mycotoxin, heavy metal
- **Controls:** testing, COA, laboratory analysis
- **Limits:** Aflatoxin <10 ppb, Pesticide within MRL

### Biological Hazards
- **Check for:** moisture, mold, pest, insect
- **Controls:** moisture meter, fumigation, sanitation
- **Limits:** Moisture <14%, Zero live insects

## Compliance Scoring

```
Score = (Present Elements Weight / Total Required Weight) × 100

Weights:
- Critical: 3
- High: 2
- Medium: 1
- Low: 0.5

Blocking: Score < 100% with any Critical gaps
```

## Gap Report Format

```markdown
# Gap Analysis Report

**Document:** [Title]
**Analyzed:** [DateTime]
**Classification:** [Type] (Confidence: X%)

## Compliance Score: X%

### ✅ Present Elements:
- Element (Clause X.X) ✓

### ❌ Missing Elements:

1. **Element Name (Clause X.X)**
   - Severity: Critical/High/Medium
   - Suggestion: [What to add]
   - Example: [Concrete text]

### 🌾 Rice Mill Hazard Coverage:
- PHYSICAL: ✅/⚠️
- CHEMICAL: ✅/⚠️
- BIOLOGICAL: ✅/⚠️

### 🔧 Recommended Actions:
1. [Action with clause reference]

**Status:** PASS / BLOCKED
```

## Interactive Workflow

After presenting report, ask user:

**If PASS (100%):**
> "Document meets all requirements. Would you like me to create a Draft record in FSMS?"

If accepted → POST to `/documents` endpoint:
```json
{
  "doc_id": "FSMS-SOP-YYYYMMDD",
  "title": "extracted title",
  "department": "detected department",
  "version": "v0.1",
  "prepared_by": "from document",
  "approved_by": "from document",
  "record_keeper": "from document",
  "iso_clauses": ["8.5.1", "7.5.2"],
  "file_path": "documents/raw/filename.pdf"
}
```

**If BLOCKED (<100% with Critical gaps):**
> "Document has X critical gaps that must be resolved:
> 1. [Gap 1]
> 2. [Gap 2]
>
> Would you like me to add the suggested text to fix these gaps?"

## Tool Integration

Use these base skills for text extraction:
- **pdf skill**: Extract text from PDF files
- **docx skill**: Extract text from Word documents

```python
# Scan for files
files = scan_raw_folder("documents/raw")

# For each file, extract text using appropriate skill
# Then analyze with gap_analyzer
```

## Example Usage

**User:** "Analyze the new SOP in documents/raw"

**Claude:**
1. Scans `documents/raw/` for files
2. Extracts text using pdf/docx skill
3. Classifies as SOP (confidence: 85%)
4. Checks 9 required elements
5. Finds 7 present, 2 missing
6. Generates report with 78% score
7. Lists missing elements with suggestions
8. Asks if user wants to add suggestions

## References

- `references/iso_22001_clauses.py` - Clause definitions and requirements
- `references/gap_analyzer_template.py` - Analysis functions and report generation

When analyzing documents, read these references for clause requirements and analysis logic.
