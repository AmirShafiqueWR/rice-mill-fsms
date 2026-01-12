"""
ISO 22001:2018 Gap Analyzer for Rice Export FSMS

This module provides document classification, gap analysis,
and compliance reporting for food safety documents.

Supports "Golden Template" format with:
- SECTION 1: DOCUMENT METADATA
- SECTION 3: OPERATIONAL PROCEDURES
- SECTION 4: HAZARD CONTROL
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

from models import VALID_DEPARTMENTS, VALID_DOC_TYPES, DEPARTMENT_CODES, DOC_TYPE_CODES


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DocumentMetadata:
    """Extracted document metadata from Golden Template SECTION 1."""
    title: str = ""
    doc_type: str = ""  # SOP, POL, REC, etc.
    prepared_by: str = ""
    approved_by: str = ""
    record_keeper: str = ""
    department: str = ""
    version: str = ""
    effective_date: str = ""
    review_date: str = ""
    extraction_confidence: float = 0.0  # 0-1 confidence score


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
    # Audit Sync validation
    audit_sync_valid: bool = True
    audit_sync_errors: list = field(default_factory=list)
    # Rice Hazard validation (SECTION 4)
    hazard_gaps: list = field(default_factory=list)


# ============================================================================
# MetadataExtractor Class (Golden Template SECTION 1)
# ============================================================================

class MetadataExtractor:
    """
    Extracts metadata from Golden Template SECTION 1.

    Golden Template Structure:
    - SECTION 1: DOCUMENT METADATA
      - Department
      - Document Type
      - Prepared By
      - Approved By
      - Record Keeper
    """

    # Section markers
    SECTION_1_PATTERNS = [
        r'SECTION\s*1[:\s]*DOCUMENT\s*METADATA',
        r'1\.0?\s*DOCUMENT\s*METADATA',
        r'DOCUMENT\s*INFORMATION',
        r'DOCUMENT\s*CONTROL\s*HEADER',
    ]

    SECTION_2_PATTERNS = [
        r'SECTION\s*2',
        r'2\.0?\s*[A-Z]',
    ]

    def __init__(self, text: str):
        """
        Initialize with document text.

        Args:
            text: Full document text
        """
        self.text = text
        self.section_1_text = self._extract_section_1()

    def _extract_section_1(self) -> str:
        """Extract SECTION 1 content from document."""
        text = self.text

        # Find start of SECTION 1
        start_pos = 0
        for pattern in self.SECTION_1_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                break

        # Find end of SECTION 1 (start of SECTION 2)
        end_pos = len(text)
        for pattern in self.SECTION_2_PATTERNS:
            match = re.search(pattern, text[start_pos:], re.IGNORECASE)
            if match:
                end_pos = start_pos + match.start()
                break

        # If no explicit section markers, use first ~2000 chars
        if start_pos == 0 and end_pos == len(text):
            end_pos = min(2000, len(text))

        return text[start_pos:end_pos]

    def extract(self) -> DocumentMetadata:
        """
        Extract all metadata from SECTION 1.

        Returns:
            DocumentMetadata object with extracted values
        """
        metadata = DocumentMetadata()
        confidence_scores = []

        # Extract each field
        metadata.title = self._extract_title()
        if metadata.title:
            confidence_scores.append(1.0)

        metadata.doc_type = self._extract_doc_type()
        if metadata.doc_type:
            confidence_scores.append(1.0)
        else:
            confidence_scores.append(0.0)

        metadata.department = self._extract_department()
        if metadata.department:
            confidence_scores.append(1.0)
        else:
            confidence_scores.append(0.0)

        metadata.prepared_by = self._extract_field(
            [r'prepared\s*by[:\s]*([^\n,;|]{2,50})',
             r'author[:\s]*([^\n,;|]{2,50})',
             r'drafted\s*by[:\s]*([^\n,;|]{2,50})']
        )
        if metadata.prepared_by:
            confidence_scores.append(1.0)
        else:
            confidence_scores.append(0.0)

        metadata.approved_by = self._extract_field(
            [r'approved\s*by[:\s]*([^\n,;|]{2,50})',
             r'authorization[:\s]*([^\n,;|]{2,50})',
             r'authorised\s*by[:\s]*([^\n,;|]{2,50})']
        )
        if metadata.approved_by:
            confidence_scores.append(1.0)
        else:
            confidence_scores.append(0.0)

        metadata.record_keeper = self._extract_field(
            [r'record\s*keeper[:\s]*([^\n,;|]{2,50})',
             r'document\s*control(?:ler)?[:\s]*([^\n,;|]{2,50})',
             r'custodian[:\s]*([^\n,;|]{2,50})']
        )
        if metadata.record_keeper:
            confidence_scores.append(1.0)
        else:
            confidence_scores.append(0.5)  # Less critical

        metadata.version = self._extract_version()
        metadata.effective_date = self._extract_date('effective')
        metadata.review_date = self._extract_date('review')

        # Calculate overall confidence
        if confidence_scores:
            metadata.extraction_confidence = sum(confidence_scores) / len(confidence_scores)

        return metadata

    def _extract_title(self) -> str:
        """Extract document title."""
        # Try explicit title field first
        patterns = [
            r'title[:\s]*([^\n]{5,100})',
            r'document\s*(?:name|title)[:\s]*([^\n]{5,100})',
        ]

        for pattern in patterns:
            match = re.search(pattern, self.section_1_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Fallback: First line with significant text
        lines = self.text.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 10 and line[0].isupper():
                # Skip section markers
                if not re.match(r'SECTION\s*\d', line, re.IGNORECASE):
                    return line[:100]

        return ""

    def _extract_doc_type(self) -> str:
        """Extract document type (SOP, POL, REC, etc.)."""
        text_to_search = self.section_1_text + " " + self.text[:500]
        text_upper = text_to_search.upper()

        # Explicit type field
        type_patterns = [
            r'document\s*type[:\s]*(\w+)',
            r'type[:\s]*(\w+)',
            r'category[:\s]*(\w+)',
        ]

        for pattern in type_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                doc_type = match.group(1).upper()
                if doc_type in VALID_DOC_TYPES:
                    return doc_type

        # Detect from content
        type_keywords = {
            'SOP': ['standard operating procedure', 'sop', 'procedure'],
            'POL': ['policy', 'food safety policy'],
            'REC': ['record', 'form', 'checklist', 'log'],
            'PF': ['process flow', 'flowchart', 'flow diagram'],
            'WI': ['work instruction', 'instruction'],
            'SPEC': ['specification', 'spec'],
            'PLAN': ['haccp plan', 'food safety plan', 'plan'],
            'MAN': ['manual', 'handbook'],
        }

        for doc_type, keywords in type_keywords.items():
            for kw in keywords:
                if kw in text_to_search.lower():
                    return doc_type

        return "SOP"  # Default

    def _extract_department(self) -> str:
        """Extract department from valid list."""
        text_to_search = self.section_1_text

        # Explicit department field
        dept_patterns = [
            r'department[:\s]*([^\n,;|]{2,30})',
            r'dept\.?[:\s]*([^\n,;|]{2,30})',
            r'division[:\s]*([^\n,;|]{2,30})',
        ]

        for pattern in dept_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                dept_text = match.group(1).strip()
                # Match to valid departments
                for valid_dept in VALID_DEPARTMENTS:
                    if valid_dept.lower() in dept_text.lower():
                        return valid_dept

        # Detect from content mentions
        dept_counts = {}
        for dept in VALID_DEPARTMENTS:
            count = len(re.findall(dept, self.text, re.IGNORECASE))
            if count > 0:
                dept_counts[dept] = count

        if dept_counts:
            return max(dept_counts, key=dept_counts.get)

        return "Quality"  # Default for FSMS documents

    def _extract_field(self, patterns: list) -> str:
        """Extract a field using multiple regex patterns."""
        for pattern in patterns:
            match = re.search(pattern, self.section_1_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Clean up common artifacts
                value = re.sub(r'\s+', ' ', value)
                value = value.strip('_\t ')
                if value and len(value) > 1:
                    return value
        return ""

    def _extract_version(self) -> str:
        """Extract version number."""
        patterns = [
            r'version[:\s]*(v?\d+\.?\d*)',
            r'rev(?:ision)?[:\s]*(v?\d+\.?\d*)',
            r'\b(v\d+\.\d+)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, self.section_1_text, re.IGNORECASE)
            if match:
                version = match.group(1)
                if not version.startswith('v'):
                    version = f"v{version}"
                # Ensure format v1.0
                if re.match(r'^v\d+$', version):
                    version = f"{version}.0"
                return version

        return "v0.1"  # Default for new documents

    def _extract_date(self, date_type: str) -> str:
        """Extract effective or review date."""
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{2}[/-]\d{2}'

        if date_type == 'effective':
            patterns = [
                rf'effective\s*(?:date)?[:\s]*({date_pattern})',
                rf'date\s*of\s*issue[:\s]*({date_pattern})',
                rf'issued?[:\s]*({date_pattern})',
            ]
        else:
            patterns = [
                rf'(?:next\s*)?review\s*(?:date)?[:\s]*({date_pattern})',
                rf'review\s*by[:\s]*({date_pattern})',
            ]

        for pattern in patterns:
            match = re.search(pattern, self.section_1_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""


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
# Metadata Extraction (Legacy wrapper - uses MetadataExtractor)
# ============================================================================

def extract_metadata(text: str) -> DocumentMetadata:
    """
    Extract document metadata from text using MetadataExtractor.

    Args:
        text: Document text

    Returns:
        DocumentMetadata object
    """
    extractor = MetadataExtractor(text)
    return extractor.extract()


# ============================================================================
# Rice Hazard Validation (Golden Template SECTION 4)
# ============================================================================

def validate_rice_hazards_section_4(text: str) -> list:
    """
    Validate SECTION 4 (Hazard Control) for rice-specific hazards.

    Rule: If Moisture, Aflatoxin, or Metal is mentioned without a numerical
    threshold, flag as 'High Severity' gap.

    Args:
        text: Full document text

    Returns:
        List of hazard gap dictionaries
    """
    hazard_gaps = []

    # Extract SECTION 4 content
    section_4_patterns = [
        r'SECTION\s*4[:\s]*HAZARD\s*CONTROL',
        r'4\.0?\s*HAZARD',
        r'HAZARD\s*(?:CONTROL|ANALYSIS|IDENTIFICATION)',
    ]

    section_5_patterns = [
        r'SECTION\s*5',
        r'5\.0?\s*[A-Z]',
    ]

    # Find SECTION 4
    section_4_start = 0
    for pattern in section_4_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            section_4_start = match.start()
            break

    # Find end (SECTION 5 or end of document)
    section_4_end = len(text)
    for pattern in section_5_patterns:
        match = re.search(pattern, text[section_4_start:], re.IGNORECASE)
        if match:
            section_4_end = section_4_start + match.start()
            break

    # Use entire document if no SECTION 4 found
    if section_4_start == 0:
        section_4_text = text
    else:
        section_4_text = text[section_4_start:section_4_end]

    section_4_lower = section_4_text.lower()

    # Rice-specific hazards requiring numerical thresholds
    critical_hazards = {
        'moisture': {
            'keywords': ['moisture', 'moisture content', 'mc'],
            'threshold_patterns': [
                r'moisture[^.]*?(\d+\.?\d*\s*%)',
                r'mc[^.]*?(\d+\.?\d*\s*%)',
                r'≤?\s*14\s*%',
                r'<\s*14\s*%',
            ],
            'expected': '≤14%',
            'risk': 'Mold growth, aflatoxin production'
        },
        'aflatoxin': {
            'keywords': ['aflatoxin', 'mycotoxin', 'aflatoxin b1'],
            'threshold_patterns': [
                r'aflatoxin[^.]*?(\d+\.?\d*\s*(?:ppb|ppm|µg/kg))',
                r'(\d+\.?\d*\s*(?:ppb|ppm))[^.]*?aflatoxin',
                r'≤?\s*10\s*ppb',
                r'<\s*10\s*ppb',
            ],
            'expected': '≤10 ppb (or ≤4 ppb for EU)',
            'risk': 'Carcinogenic mycotoxin, export rejection'
        },
        'metal': {
            'keywords': ['metal', 'metal fragment', 'metal detection', 'metal detector'],
            'threshold_patterns': [
                r'metal[^.]*?(\d+\.?\d*\s*(?:mm|cm))',
                r'(\d+\.?\d*\s*mm)[^.]*?metal',
                r'ferrous[^.]*?(\d+\.?\d*\s*mm)',
                r'non-ferrous[^.]*?(\d+\.?\d*\s*mm)',
            ],
            'expected': 'Ferrous: ≤1.5mm, Non-ferrous: ≤2.0mm, Stainless: ≤2.5mm',
            'risk': 'Physical contamination, consumer injury'
        },
    }

    for hazard_type, config in critical_hazards.items():
        # Check if hazard is mentioned
        hazard_mentioned = any(kw in section_4_lower for kw in config['keywords'])

        if hazard_mentioned:
            # Check if numerical threshold is present
            has_threshold = False
            for pattern in config['threshold_patterns']:
                if re.search(pattern, section_4_text, re.IGNORECASE):
                    has_threshold = True
                    break

            if not has_threshold:
                hazard_gaps.append({
                    'hazard': hazard_type.title(),
                    'severity': 'High',
                    'issue': f'{hazard_type.title()} mentioned without numerical threshold',
                    'expected_threshold': config['expected'],
                    'risk': config['risk'],
                    'suggestion': f'Add critical limit for {hazard_type}: {config["expected"]}',
                    'iso_clause': '8.5.1.2'
                })

    return hazard_gaps


# ============================================================================
# Audit Sync Validation
# ============================================================================

def validate_audit_sync(
    extracted_metadata: DocumentMetadata,
    db_metadata: dict = None
) -> tuple[bool, list]:
    """
    Cross-verify document text metadata against database metadata.

    Rule: If 'Approved By' in document doesn't match database value,
    trigger 'Blocking Gap' and set Compliance Score to 0%.

    Args:
        extracted_metadata: Metadata extracted from document text
        db_metadata: Metadata from database (optional for new documents)

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    if db_metadata is None:
        # New document - no sync needed
        return True, []

    # Critical field: Approved By must match
    db_approved_by = db_metadata.get('approved_by', '').strip().lower()
    doc_approved_by = extracted_metadata.approved_by.strip().lower()

    if db_approved_by and doc_approved_by:
        # Both have values - must match
        if db_approved_by != doc_approved_by:
            errors.append({
                'field': 'approved_by',
                'severity': 'Blocking',
                'document_value': extracted_metadata.approved_by,
                'database_value': db_metadata.get('approved_by'),
                'message': f"BLOCKING GAP: 'Approved By' mismatch. Document: '{extracted_metadata.approved_by}' vs Database: '{db_metadata.get('approved_by')}'"
            })

    # Other fields - warning only
    field_checks = [
        ('prepared_by', 'Prepared By'),
        ('department', 'Department'),
        ('record_keeper', 'Record Keeper'),
    ]

    for field_key, field_name in field_checks:
        db_value = db_metadata.get(field_key, '').strip().lower()
        doc_value = getattr(extracted_metadata, field_key, '').strip().lower()

        if db_value and doc_value and db_value != doc_value:
            errors.append({
                'field': field_key,
                'severity': 'Warning',
                'document_value': getattr(extracted_metadata, field_key),
                'database_value': db_metadata.get(field_key),
                'message': f"Warning: '{field_name}' mismatch. Document: '{getattr(extracted_metadata, field_key)}' vs Database: '{db_metadata.get(field_key)}'"
            })

    # Check if any blocking errors
    has_blocking = any(e['severity'] == 'Blocking' for e in errors)

    return not has_blocking, errors


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

def analyze_document(
    file_path: str,
    text: str,
    db_metadata: dict = None
) -> GapAnalysisResult:
    """
    Perform complete gap analysis on a document.

    Args:
        file_path: Path to the document file
        text: Extracted document text
        db_metadata: Optional metadata from database for audit sync validation

    Returns:
        GapAnalysisResult object
    """
    # Classify document
    doc_type, confidence = classify_document(text)

    # Extract metadata using MetadataExtractor (Golden Template SECTION 1)
    metadata = extract_metadata(text)

    # Override doc_type from metadata if extracted
    if metadata.doc_type:
        # Map internal doc_type to classification type for compatibility
        type_mapping = {
            'SOP': 'SOP',
            'POL': 'POLICY',
            'REC': 'RECORD',
            'PF': 'PROCESS_FLOW',
            'WI': 'SOP',
            'SPEC': 'SOP',
            'PLAN': 'SOP',
            'MAN': 'POLICY',
        }
        doc_type = type_mapping.get(metadata.doc_type, doc_type)

    # Check required elements
    present, missing = check_required_elements(text, doc_type, metadata)

    # Calculate compliance score
    score = calculate_compliance_score(present, missing)

    # Get blocking gaps from missing elements
    blocking = get_blocking_gaps(missing)

    # Check rice mill hazards
    hazards = check_rice_mill_hazards(text)

    # Validate rice hazards in SECTION 4 (High Severity gaps)
    hazard_gaps = validate_rice_hazards_section_4(text)

    # Add hazard gaps to missing elements with High severity
    for gap in hazard_gaps:
        missing.append((gap['issue'], gap['iso_clause'], 'High'))

    # Audit Sync Validation
    audit_sync_valid, audit_sync_errors = validate_audit_sync(metadata, db_metadata)

    # If audit sync fails (Approved By mismatch), set compliance to 0% and block
    if not audit_sync_valid:
        score = 0.0
        for error in audit_sync_errors:
            if error['severity'] == 'Blocking':
                blocking.append((error['message'], '7.5.3', 'Blocking'))

    # Generate suggestions
    suggestions = generate_suggestions(missing, doc_type)

    # Add hazard gap suggestions
    for gap in hazard_gaps:
        suggestions.append({
            'element': gap['hazard'],
            'clause': gap['iso_clause'],
            'severity': gap['severity'],
            'suggestion': gap['suggestion'],
            'example': f"Critical Limit: {gap['expected_threshold']}"
        })

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
        is_blocked=len(blocking) > 0 or not audit_sync_valid,
        suggestions=suggestions,
        audit_sync_valid=audit_sync_valid,
        audit_sync_errors=audit_sync_errors,
        hazard_gaps=hazard_gaps
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

async def create_draft_record(
    result: GapAnalysisResult,
    api_base: str = "http://localhost:8000"
) -> dict:
    """
    Create a Draft document record via FastAPI endpoint.

    Uses extracted metadata from Golden Template SECTION 1 to auto-fill
    the database record. System generates the doc_id automatically based
    on department and doc_type.

    Args:
        result: GapAnalysisResult object
        api_base: Base URL for the API

    Returns:
        API response dictionary with auto-generated doc_id
    """
    # Map document classification type to doc_type code
    doc_type_mapping = {
        "POLICY": "POL",
        "SOP": "SOP",
        "PROCESS_FLOW": "PF",
        "RECORD": "REC"
    }

    # Use extracted doc_type from metadata, or map from classification
    doc_type = result.metadata.doc_type or doc_type_mapping.get(result.document_type, "SOP")

    # Collect ISO clauses from present elements
    iso_clauses = list(set(clause for _, clause, _ in result.present_elements))

    # Build payload using extracted metadata - NO doc_id (system generates it)
    payload = {
        # doc_id is NOT included - system auto-generates based on dept + type
        "doc_type": doc_type,
        "title": result.metadata.title or result.file_name,
        "department": result.metadata.department or "Quality",
        "version": result.metadata.version or "v0.1",
        "prepared_by": result.metadata.prepared_by or "",
        "approved_by": result.metadata.approved_by or "",
        "record_keeper": result.metadata.record_keeper or "",
        "iso_clauses": iso_clauses,
        "file_path": result.file_path
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{api_base}/documents", json=payload)
        return response.json()


async def create_draft_from_file(
    file_path: str,
    text: str,
    api_base: str = "http://localhost:8000"
) -> dict:
    """
    Convenience function to analyze a file and create a Draft record.

    Combines gap analysis with automatic Draft creation using
    extracted metadata from Golden Template.

    Args:
        file_path: Path to the document file
        text: Extracted document text
        api_base: Base URL for the API

    Returns:
        Dictionary with analysis result and API response
    """
    # Analyze document
    result = analyze_document(file_path, text)

    # Check if document passes minimum requirements
    if result.is_blocked:
        return {
            "success": False,
            "error": "Document has blocking gaps",
            "blocking_gaps": result.blocking_gaps,
            "compliance_score": result.compliance_score,
            "analysis": result
        }

    # Create Draft record with auto-generated ID
    try:
        api_response = await create_draft_record(result, api_base)
        return {
            "success": True,
            "doc_id": api_response.get("doc_id"),
            "document_id": api_response.get("id"),
            "metadata_extracted": {
                "title": result.metadata.title,
                "department": result.metadata.department,
                "doc_type": result.metadata.doc_type,
                "prepared_by": result.metadata.prepared_by,
                "approved_by": result.metadata.approved_by,
                "record_keeper": result.metadata.record_keeper,
                "extraction_confidence": result.metadata.extraction_confidence
            },
            "compliance_score": result.compliance_score,
            "api_response": api_response
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "analysis": result
        }


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
