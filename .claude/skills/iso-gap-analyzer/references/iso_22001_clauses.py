"""
ISO 22001:2018 Clause Definitions and Requirements

This module contains the clause structure and requirements
for Food Safety Management Systems compliance checking.
"""

# ============================================================================
# ISO 22001:2018 Clause Structure
# ============================================================================

ISO_CLAUSES = {
    # Clause 5: Leadership
    "5.2": {
        "title": "Food Safety Policy",
        "description": "Top management shall establish, implement and maintain a food safety policy",
        "requirements": [
            "Appropriate to purpose and context",
            "Provides framework for objectives",
            "Includes commitment to meet requirements",
            "Includes commitment to continual improvement",
            "Communicated within organization",
            "Available to interested parties"
        ]
    },
    "5.2.1": {
        "title": "Establishing the Food Safety Policy",
        "description": "Management commitment to food safety",
        "requirements": [
            "Food safety commitment statement",
            "Measurable objectives defined",
            "Legal compliance commitment"
        ]
    },
    "5.2.2": {
        "title": "Communicating the Food Safety Policy",
        "description": "Policy communication requirements",
        "requirements": [
            "Maintained as documented information",
            "Communicated to all levels",
            "Available to relevant interested parties"
        ]
    },
    "5.3": {
        "title": "Organizational Roles, Responsibilities and Authorities",
        "description": "Top management shall ensure responsibilities and authorities are assigned",
        "requirements": [
            "Roles defined for FSMS",
            "Responsibilities documented",
            "Authorities assigned and communicated",
            "Food safety team leader appointed"
        ]
    },

    # Clause 7: Support
    "7.5.2": {
        "title": "Creating and Updating Documented Information",
        "description": "Requirements for document creation and updates",
        "requirements": [
            "Appropriate identification (title, date, author)",
            "Appropriate format (language, version)",
            "Review and approval for suitability"
        ]
    },
    "7.5.3": {
        "title": "Control of Documented Information",
        "description": "Document control requirements",
        "requirements": [
            "Available and suitable for use",
            "Adequately protected",
            "Distribution and access controlled",
            "Storage and preservation ensured",
            "Retention and disposition defined",
            "Changes controlled"
        ]
    },

    # Clause 8: Operation
    "8.1": {
        "title": "Operational Planning and Control",
        "description": "Plan, implement and control processes for food safety",
        "requirements": [
            "Criteria for processes established",
            "Process controls implemented",
            "Documented information maintained"
        ]
    },
    "8.5.1": {
        "title": "Control of Hazards (HACCP Principles)",
        "description": "Hazard analysis and critical control points",
        "requirements": [
            "Hazard identification",
            "Hazard assessment (likelihood, severity)",
            "Control measures identified",
            "CCP determination",
            "Critical limits established"
        ]
    },
    "8.5.1.2": {
        "title": "Determination of Critical Limits",
        "description": "Critical limits for each CCP",
        "requirements": [
            "Measurable critical limits",
            "Scientific rationale documented",
            "Regulatory requirements considered",
            "Limits ensure food safety"
        ]
    },
    "8.5.1.3": {
        "title": "Monitoring System at CCPs",
        "description": "Monitoring procedures for each CCP",
        "requirements": [
            "Monitoring methods specified",
            "Monitoring frequency defined",
            "Responsible personnel assigned",
            "Records maintained"
        ]
    },
    "8.5.1.4": {
        "title": "Actions When Critical Limits Exceeded",
        "description": "Corrective actions when monitoring shows deviation",
        "requirements": [
            "Corrective actions defined",
            "Product disposition addressed",
            "Root cause analysis required",
            "Records of actions maintained"
        ]
    }
}


# ============================================================================
# Document Type Definitions
# ============================================================================

DOCUMENT_TYPES = {
    "POLICY": {
        "keywords": ["policy", "commitment", "management responsibility", "shall ensure",
                     "organization shall", "top management", "food safety policy"],
        "typical_pages": (2, 5),
        "characteristics": [
            "High-level language",
            "No step-by-step instructions",
            "Management commitment statements",
            "Scope and applicability defined"
        ],
        "required_elements": [
            ("Food safety commitment", "5.2.1", "Critical"),
            ("Regulatory compliance statement", "5.2.2", "Critical"),
            ("Roles and responsibilities", "5.3", "High"),
            ("Document control metadata", "7.5.2", "High"),
            ("Prepared By field", "7.5.2", "High"),
            ("Approved By field", "7.5.2", "High"),
            ("Review date", "7.5.3", "Medium")
        ]
    },
    "SOP": {
        "keywords": ["procedure", "shall", "step", "instruction", "work instruction",
                     "standard operating", "sop", "steps:", "procedure:"],
        "typical_pages": (3, 15),
        "characteristics": [
            "Numbered steps (1. 2. 3. or Step 1, Step 2)",
            "Action-oriented language",
            "Clear responsibilities",
            "Sequential instructions"
        ],
        "required_elements": [
            ("Prepared By field", "7.5.2", "Critical"),
            ("Approved By field", "7.5.2", "Critical"),
            ("Department specified", "5.3", "Critical"),
            ("Hazard identification", "8.5.1", "Critical"),
            ("Critical limits (if HACCP)", "8.5.1.2", "High"),
            ("Monitoring frequency", "8.5.1.3", "High"),
            ("Corrective actions", "8.5.1.4", "High"),
            ("Version number", "7.5.3", "Medium"),
            ("Effective date", "7.5.3", "Medium")
        ]
    },
    "PROCESS_FLOW": {
        "keywords": ["input", "output", "decision point", "flowchart", "process flow",
                     "decision", "yes/no", "start", "end", "subprocess"],
        "typical_pages": (1, 5),
        "characteristics": [
            "Contains diagrams or flowchart elements",
            "Visual decision trees",
            "Process steps connected",
            "Inputs and outputs defined"
        ],
        "required_elements": [
            ("Process inputs defined", "8.1", "High"),
            ("Process outputs defined", "8.1", "High"),
            ("Decision criteria", "8.1", "High"),
            ("CCPs identified", "8.5.1", "Critical"),
            ("Document control", "7.5.2", "Medium")
        ]
    },
    "RECORD": {
        "keywords": ["date", "time", "checked by", "signature", "initials", "verified by",
                     "inspector", "batch", "lot number", "record", "log", "form"],
        "typical_pages": (1, 3),
        "characteristics": [
            "Contains tables",
            "Checkboxes or tick boxes",
            "Signature lines",
            "Form-like structure"
        ],
        "required_elements": [
            ("Date field", "7.5.3", "Critical"),
            ("Responsible person field", "5.3", "Critical"),
            ("Measurement fields", "8.5.1.3", "High"),
            ("Verification signature", "7.5.2", "High"),
            ("Retention period", "7.5.3", "Medium")
        ]
    }
}


# ============================================================================
# Rice Mill Specific Hazards
# ============================================================================

RICE_MILL_HAZARDS = {
    "PHYSICAL": {
        "hazard_keywords": ["stone", "metal", "magnet", "sieve", "screen", "foreign object",
                           "glass", "wood", "plastic fragment", "string", "hair"],
        "control_keywords": ["magnetic separator", "sifter", "destoner", "visual inspection",
                            "metal detector", "x-ray", "screening", "gravity separator"],
        "critical_limits": [
            "Metal: <2mm diameter",
            "Stone: Zero tolerance",
            "Glass: Zero tolerance"
        ]
    },
    "CHEMICAL": {
        "hazard_keywords": ["pesticide", "aflatoxin", "mycotoxin", "residue", "contamination",
                           "heavy metal", "lead", "arsenic", "cadmium", "herbicide", "fumigant"],
        "control_keywords": ["testing", "certificate", "ppb limit", "laboratory analysis",
                            "supplier verification", "coa", "certificate of analysis",
                            "sampling", "batch testing"],
        "critical_limits": [
            "Aflatoxin: <10 ppb (total)",
            "Aflatoxin B1: <5 ppb",
            "Pesticide residue: Within MRL",
            "Heavy metals: Within regulatory limits"
        ]
    },
    "BIOLOGICAL": {
        "hazard_keywords": ["moisture", "mold", "humidity", "pest", "insect", "rodent",
                           "bacteria", "microbiological", "pathogen", "contamination"],
        "control_keywords": ["moisture meter", "fumigation", "inspection", "sanitation",
                            "pest control", "ipm", "cleaning", "disinfection", "temperature control"],
        "critical_limits": [
            "Moisture: <14%",
            "Temperature: <25°C storage",
            "Relative humidity: <70%",
            "Insect count: Zero live insects"
        ]
    }
}


# ============================================================================
# Compliance Scoring
# ============================================================================

SEVERITY_WEIGHTS = {
    "Critical": 3,
    "High": 2,
    "Medium": 1,
    "Low": 0.5
}


def calculate_compliance_score(present_elements: list, missing_elements: list) -> float:
    """
    Calculate weighted compliance score.

    Args:
        present_elements: List of (element_name, clause, severity) tuples
        missing_elements: List of (element_name, clause, severity) tuples

    Returns:
        Compliance percentage (0-100)
    """
    total_weight = sum(SEVERITY_WEIGHTS.get(e[2], 1) for e in present_elements + missing_elements)
    present_weight = sum(SEVERITY_WEIGHTS.get(e[2], 1) for e in present_elements)

    if total_weight == 0:
        return 100.0

    return round((present_weight / total_weight) * 100, 1)


def get_blocking_gaps(missing_elements: list) -> list:
    """
    Get elements that block progression (Critical severity).

    Args:
        missing_elements: List of (element_name, clause, severity) tuples

    Returns:
        List of blocking gaps
    """
    return [e for e in missing_elements if e[2] == "Critical"]
