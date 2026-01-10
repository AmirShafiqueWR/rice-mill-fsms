"""
ISO 22001:2018 Gap Analyzer for Rice Export FSMS

This module provides document classification, gap analysis,
and compliance reporting for food safety documents.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import httpx

from iso_22001_clauses import (
    ISO_CLAUSES,
    DOCUMENT_TYPES,
    RICE_MILL_HAZARDS,
    calculate_compliance_score,
    get_blocking_gaps,
    SEVERITY_WEIGHTS
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DocumentMetadata:
    """Extracted document metadata."""
    title: str = ""
    prepared_by: str = ""
    approved_by: str = ""
    record_keeper: str = ""
    department: str = ""
    version: str = ""
    effective_date: str = ""
    review_date: str = ""


@dataclass
class GapAnalysisResult:
    """Result of gap analysis."""
    file_path: str
    file_name: str
    document_type: str
    classification_confidence: float
    compliance_score: float
    present_elements: list = field(default_factory=list)
    missing_elements: list = field(default_factory=list)
    hazards_found: dict = field(default_factory=dict)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    blocking_gaps: list = field(default_factory=list)
    is_blocked: bool = False
    suggestions: list = field(default_factory=list)


# ============================================================================
# Document Classification
# ============================================================================

def classify_document(text: str) -> tuple[str, float]:
    """
    Classify document type based on keywords and structure.

    Args:
        text: Extracted document text

    Returns:
        Tuple of (document_type, confidence_score)
    """
    text_lower = text.lower()
    scores = {}

    for doc_type, config in DOCUMENT_TYPES.items():
        score = 0
        keyword_matches = 0

        # Check keyword matches
        for keyword in config["keywords"]:
            if keyword.lower() in text_lower:
                keyword_matches += 1

        # Calculate keyword score (0-50 points)
        keyword_score = min(50, (keyword_matches / len(config["keywords"])) * 100)
        score += keyword_score

        # Check structural indicators (0-50 points)
        structure_score = 0

        if doc_type == "SOP":
            # Check for numbered steps
            if re.search(r'(?:step\s*\d|^\s*\d+\.\s+\w)', text_lower, re.MULTILINE):
                structure_score += 25
            if re.search(r'(?:shall|must|ensure)', text_lower):
                structure_score += 15
            if re.search(r'(?:responsible|responsibility)', text_lower):
                structure_score += 10

        elif doc_type == "POLICY":
            if re.search(r'(?:commit|commitment)', text_lower):
                structure_score += 20
            if re.search(r'(?:scope|purpose|objective)', text_lower):
                structure_score += 15
            if re.search(r'(?:management|leadership)', text_lower):
                structure_score += 15

        elif doc_type == "PROCESS_FLOW":
            if re.search(r'(?:→|->|yes.*no|input.*output)', text_lower):
                structure_score += 25
            if re.search(r'(?:start|end|begin|finish)', text_lower):
                structure_score += 15

        elif doc_type == "RECORD":
            # Check for table-like structures
            if re.search(r'(?:\|.*\||\t.*\t)', text):
                structure_score += 20
            if re.search(r'(?:date:?|time:?|signature:?|batch)', text_lower):
                structure_score += 20
            if re.search(r'(?:□|☐|☑|✓|✔)', text):
                structure_score += 10

        score += structure_score
        scores[doc_type] = score

    # Get highest scoring type
    best_type = max(scores, key=scores.get)
    confidence = min(100, scores[best_type]) / 100

    return best_type, confidence


# ============================================================================
# Metadata Extraction
# ============================================================================

def extract_metadata(text: str) -> DocumentMetadata:
    """
    Extract document metadata from text.

    Args:
        text: Document text

    Returns:
        DocumentMetadata object
    """
    metadata = DocumentMetadata()

    # Title extraction (usually first non-empty line or after "Title:")
    title_match = re.search(r'(?:title:?\s*|^)([A-Z][^\n]{5,100})', text, re.MULTILINE | re.IGNORECASE)
    if title_match:
        metadata.title = title_match.group(1).strip()

    # Prepared By
    prep_match = re.search(r'prepared\s*(?:by)?:?\s*([^\n,;]{2,50})', text, re.IGNORECASE)
    if prep_match:
        metadata.prepared_by = prep_match.group(1).strip()

    # Approved By
    appr_match = re.search(r'approved\s*(?:by)?:?\s*([^\n,;]{2,50})', text, re.IGNORECASE)
    if appr_match:
        metadata.approved_by = appr_match.group(1).strip()

    # Record Keeper / Document Controller
    keeper_match = re.search(r'(?:record\s*keeper|document\s*control(?:ler)?):?\s*([^\n,;]{2,50})', text, re.IGNORECASE)
    if keeper_match:
        metadata.record_keeper = keeper_match.group(1).strip()

    # Department
    dept_match = re.search(r'department:?\s*([^\n,;]{2,30})', text, re.IGNORECASE)
    if dept_match:
        metadata.department = dept_match.group(1).strip()
    else:
        # Try to detect from content
        departments = ["Milling", "Quality", "Exports", "Packaging", "Storage"]
        for dept in departments:
            if dept.lower() in text.lower():
                metadata.department = dept
                break

    # Version
    ver_match = re.search(r'(?:version|rev|revision):?\s*(v?\d+\.?\d*)', text, re.IGNORECASE)
    if ver_match:
        version = ver_match.group(1)
        if not version.startswith('v'):
            version = f"v{version}"
        metadata.version = version

    # Dates
    date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{2}[/-]\d{2}'

    eff_match = re.search(rf'effective\s*(?:date)?:?\s*({date_pattern})', text, re.IGNORECASE)
    if eff_match:
        metadata.effective_date = eff_match.group(1)

    rev_match = re.search(rf'(?:review|next\s*review)\s*(?:date)?:?\s*({date_pattern})', text, re.IGNORECASE)
    if rev_match:
        metadata.review_date = rev_match.group(1)

    return metadata


# ============================================================================
# Gap Analysis
# ============================================================================

def check_required_elements(text: str, doc_type: str, metadata: DocumentMetadata) -> tuple[list, list]:
    """
    Check for required elements based on document type.

    Args:
        text: Document text
        doc_type: Classified document type
        metadata: Extracted metadata

    Returns:
        Tuple of (present_elements, missing_elements)
    """
    present = []
    missing = []
    text_lower = text.lower()

    required = DOCUMENT_TYPES[doc_type]["required_elements"]

    for element_name, clause, severity in required:
        found = False

        # Check based on element type
        if "Prepared By" in element_name:
            found = bool(metadata.prepared_by)
        elif "Approved By" in element_name:
            found = bool(metadata.approved_by)
        elif "Department" in element_name:
            found = bool(metadata.department)
        elif "Version" in element_name:
            found = bool(metadata.version)
        elif "Date field" in element_name:
            found = bool(re.search(r'date:?\s*[_/\-\d]', text_lower))
        elif "commitment" in element_name.lower():
            found = "commit" in text_lower and "food safety" in text_lower
        elif "Regulatory compliance" in element_name:
            found = any(kw in text_lower for kw in ["regulatory", "legal", "compliance", "statutory"])
        elif "Roles and responsibilities" in element_name:
            found = "responsib" in text_lower
        elif "Document control" in element_name:
            found = any(kw in text_lower for kw in ["document control", "controlled copy", "revision"])
        elif "Hazard identification" in element_name:
            found = any(kw in text_lower for kw in ["hazard", "risk", "ccp", "critical control"])
        elif "Critical limits" in element_name:
            found = any(kw in text_lower for kw in ["critical limit", "limit", "max", "min", "tolerance"])
        elif "Monitoring frequency" in element_name:
            found = any(kw in text_lower for kw in ["monitor", "frequency", "every", "per batch", "hourly", "daily"])
        elif "Corrective action" in element_name:
            found = any(kw in text_lower for kw in ["corrective", "action", "if", "when", "deviation"])
        elif "Process inputs" in element_name:
            found = "input" in text_lower
        elif "Process outputs" in element_name:
            found = "output" in text_lower
        elif "Decision criteria" in element_name:
            found = any(kw in text_lower for kw in ["decision", "if", "then", "criteria"])
        elif "CCP" in element_name:
            found = any(kw in text_lower for kw in ["ccp", "critical control point", "critical point"])
        elif "Responsible person" in element_name:
            found = any(kw in text_lower for kw in ["responsible", "inspector", "supervisor", "checked by"])
        elif "Measurement" in element_name:
            found = any(kw in text_lower for kw in ["measure", "reading", "value", "result", "temperature", "moisture"])
        elif "Verification" in element_name:
            found = any(kw in text_lower for kw in ["verify", "verified", "signature", "approval"])
        elif "Retention" in element_name:
            found = any(kw in text_lower for kw in ["retention", "keep for", "years", "archive"])
        elif "Effective date" in element_name:
            found = bool(metadata.effective_date)
        elif "Review date" in element_name:
            found = bool(metadata.review_date)

        if found:
            present.append((element_name, clause, severity))
        else:
            missing.append((element_name, clause, severity))

    return present, missing


def check_rice_mill_hazards(text: str) -> dict:
    """
    Check for rice mill specific hazard controls.

    Args:
        text: Document text

    Returns:
        Dictionary of hazard categories with findings
    """
    text_lower = text.lower()
    findings = {}

    for hazard_type, config in RICE_MILL_HAZARDS.items():
        hazards_mentioned = []
        controls_mentioned = []
        limits_mentioned = []

        # Check for hazard keywords
        for kw in config["hazard_keywords"]:
            if kw in text_lower:
                hazards_mentioned.append(kw)

        # Check for control keywords
        for kw in config["control_keywords"]:
            if kw in text_lower:
                controls_mentioned.append(kw)

        # Check for critical limits
        for limit in config["critical_limits"]:
            # Extract the numeric part for searching
            if any(part.lower() in text_lower for part in limit.split(":")):
                limits_mentioned.append(limit)

        if hazards_mentioned or controls_mentioned:
            findings[hazard_type] = {
                "hazards": hazards_mentioned,
                "controls": controls_mentioned,
                "limits": limits_mentioned,
                "has_control": len(controls_mentioned) > 0,
                "has_limits": len(limits_mentioned) > 0
            }

    return findings


def generate_suggestions(missing_elements: list, doc_type: str) -> list:
    """
    Generate specific suggestions for missing elements.

    Args:
        missing_elements: List of (element_name, clause, severity) tuples
        doc_type: Document type

    Returns:
        List of suggestion dictionaries
    """
    suggestions = []

    suggestion_templates = {
        "Prepared By field": {
            "text": "Add 'Prepared By: [Name, Role]' in the document header",
            "example": "Prepared By: John Smith, Quality Manager"
        },
        "Approved By field": {
            "text": "Add 'Approved By: [Name, Role]' in the document header",
            "example": "Approved By: Jane Doe, Plant Director"
        },
        "Department specified": {
            "text": "Add 'Department: [Department Name]' in the document header",
            "example": "Department: Quality Assurance"
        },
        "Hazard identification": {
            "text": "Add a 'Hazard Analysis' section identifying relevant hazards (physical, chemical, biological)",
            "example": "3.0 Hazard Analysis\n3.1 Physical Hazards: Stones, metal fragments\n3.2 Chemical Hazards: Pesticide residue, aflatoxin\n3.3 Biological Hazards: Mold, insects"
        },
        "Critical limits (if HACCP)": {
            "text": "Specify measurable critical limits for each control point",
            "example": "Critical Limits:\n- Moisture content: ≤14%\n- Temperature: ≤25°C\n- Metal detection: No fragments >2mm"
        },
        "Monitoring frequency": {
            "text": "Define how often each control point should be monitored",
            "example": "Monitoring Frequency:\n- Moisture: Every batch\n- Temperature: Every 4 hours\n- Metal detection: Continuous"
        },
        "Corrective actions": {
            "text": "Add corrective action procedures for when limits are exceeded",
            "example": "Corrective Actions:\n- If moisture >14%: Hold batch, re-dry, re-test before release\n- If metal detected: Stop line, investigate source, dispose affected product"
        },
        "Food safety commitment": {
            "text": "Add management commitment statement to food safety",
            "example": "[Company Name] is committed to producing safe, high-quality rice products that meet all regulatory requirements and customer expectations."
        },
        "Regulatory compliance statement": {
            "text": "Add statement confirming compliance with food safety regulations",
            "example": "This policy ensures compliance with [Country] Food Safety Act, Codex Alimentarius guidelines, and ISO 22001:2018 requirements."
        },
        "Roles and responsibilities": {
            "text": "Define who is responsible for food safety activities",
            "example": "Responsibilities:\n- Plant Director: Overall FSMS accountability\n- Quality Manager: Food safety team leader\n- Supervisors: Daily monitoring and verification"
        },
        "Version number": {
            "text": "Add version control information",
            "example": "Version: v1.0"
        }
    }

    for element_name, clause, severity in missing_elements:
        template = suggestion_templates.get(element_name, {
            "text": f"Add section addressing {element_name}",
            "example": f"[Add {element_name} content here]"
        })

        suggestions.append({
            "element": element_name,
            "clause": clause,
            "severity": severity,
            "suggestion": template["text"],
            "example": template["example"]
        })

    return suggestions


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_document(file_path: str, text: str) -> GapAnalysisResult:
    """
    Perform complete gap analysis on a document.

    Args:
        file_path: Path to the document file
        text: Extracted document text

    Returns:
        GapAnalysisResult object
    """
    # Classify document
    doc_type, confidence = classify_document(text)

    # Extract metadata
    metadata = extract_metadata(text)

    # Check required elements
    present, missing = check_required_elements(text, doc_type, metadata)

    # Calculate compliance score
    score = calculate_compliance_score(present, missing)

    # Get blocking gaps
    blocking = get_blocking_gaps(missing)

    # Check rice mill hazards
    hazards = check_rice_mill_hazards(text)

    # Generate suggestions
    suggestions = generate_suggestions(missing, doc_type)

    return GapAnalysisResult(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        document_type=doc_type,
        classification_confidence=confidence,
        compliance_score=score,
        present_elements=present,
        missing_elements=missing,
        hazards_found=hazards,
        metadata=metadata,
        blocking_gaps=blocking,
        is_blocked=len(blocking) > 0,
        suggestions=suggestions
    )


# ============================================================================
# Report Generation
# ============================================================================

def generate_gap_report(result: GapAnalysisResult) -> str:
    """
    Generate markdown gap analysis report.

    Args:
        result: GapAnalysisResult object

    Returns:
        Markdown formatted report string
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Gap Analysis Report

**Document:** {result.metadata.title or result.file_name}
**File:** {result.file_path}
**Analyzed:** {now}
**Classification:** {result.document_type} (Confidence: {result.classification_confidence:.0%})

## Compliance Score: {result.compliance_score}%

"""

    # Present elements
    if result.present_elements:
        report += "### ✅ Present Elements:\n"
        for element, clause, severity in result.present_elements:
            report += f"- {element} (Clause {clause}) ✓\n"
        report += "\n"

    # Missing elements
    if result.missing_elements:
        report += "### ❌ Missing Elements:\n\n"
        for i, (element, clause, severity) in enumerate(result.missing_elements, 1):
            suggestion = next((s for s in result.suggestions if s["element"] == element), None)
            report += f"""**{i}. {element} (Clause {clause})**
- Severity: {severity}
- Suggestion: {suggestion["suggestion"] if suggestion else "Add required content"}
- Example:
```
{suggestion["example"] if suggestion else "N/A"}
```

"""

    # Rice mill hazards
    if result.hazards_found:
        report += "### 🌾 Rice Mill Hazard Coverage:\n\n"
        for hazard_type, data in result.hazards_found.items():
            status = "✅" if data["has_control"] else "⚠️"
            report += f"**{hazard_type} Hazards** {status}\n"
            if data["hazards"]:
                report += f"- Hazards mentioned: {', '.join(data['hazards'])}\n"
            if data["controls"]:
                report += f"- Controls mentioned: {', '.join(data['controls'])}\n"
            if data["limits"]:
                report += f"- Limits specified: {', '.join(data['limits'])}\n"
            if not data["has_control"]:
                report += f"- ⚠️ Missing: Control measures for identified hazards\n"
            report += "\n"

    # Recommended actions
    if result.missing_elements:
        report += "### 🔧 Recommended Actions:\n"
        for i, (element, clause, severity) in enumerate(result.missing_elements, 1):
            report += f"{i}. Add {element} (Reference: ISO 22001:2018 Clause {clause})\n"
        report += "\n"

    # Status
    if result.is_blocked:
        report += f"""**Status:** ❌ BLOCKED

**Reason:** The following critical elements are missing:
"""
        for element, clause, severity in result.blocking_gaps:
            report += f"- {element} (Clause {clause})\n"
        report += "\nDocument cannot progress until all critical gaps are resolved.\n"
    elif result.compliance_score < 100:
        report += f"""**Status:** ⚠️ CONDITIONAL PASS

Document has non-critical gaps. Can proceed with caution, but gaps should be addressed.
"""
    else:
        report += f"""**Status:** ✅ PASS

Document meets all requirements. Ready to create Draft record in FSMS.
"""

    # Metadata summary
    report += f"""
---
## Extracted Metadata:
- Title: {result.metadata.title or "Not found"}
- Department: {result.metadata.department or "Not found"}
- Prepared By: {result.metadata.prepared_by or "Not found"}
- Approved By: {result.metadata.approved_by or "Not found"}
- Version: {result.metadata.version or "Not found"}
"""

    return report


# ============================================================================
# API Integration
# ============================================================================

async def create_draft_record(result: GapAnalysisResult, api_base: str = "http://localhost:8000") -> dict:
    """
    Create a Draft document record via FastAPI endpoint.

    Args:
        result: GapAnalysisResult object
        api_base: Base URL for the API

    Returns:
        API response dictionary
    """
    # Generate doc_id based on document type
    doc_type_prefix = {
        "POLICY": "POL",
        "SOP": "SOP",
        "PROCESS_FLOW": "PF",
        "RECORD": "REC"
    }
    prefix = doc_type_prefix.get(result.document_type, "DOC")

    # Get next number (would normally query DB)
    doc_id = f"FSMS-{prefix}-{datetime.now().strftime('%Y%m%d%H%M')}"

    # Collect ISO clauses from present elements
    iso_clauses = list(set(clause for _, clause, _ in result.present_elements))

    payload = {
        "doc_id": doc_id,
        "title": result.metadata.title or result.file_name,
        "department": result.metadata.department or "Quality",
        "version": result.metadata.version or "v0.1",
        "prepared_by": result.metadata.prepared_by or "To be assigned",
        "approved_by": result.metadata.approved_by or "To be assigned",
        "record_keeper": result.metadata.record_keeper or "Document Control",
        "iso_clauses": iso_clauses,
        "file_path": result.file_path
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{api_base}/documents", json=payload)
        return response.json()


# ============================================================================
# File Scanner
# ============================================================================

def scan_raw_folder(folder_path: str = "documents/raw") -> list[str]:
    """
    Scan folder for documents to analyze.

    Args:
        folder_path: Path to folder containing raw documents

    Returns:
        List of file paths
    """
    supported_extensions = [".pdf", ".docx", ".doc", ".txt"]
    files = []

    path = Path(folder_path)
    if path.exists():
        for ext in supported_extensions:
            files.extend(str(f) for f in path.glob(f"*{ext}"))

    return sorted(files)
