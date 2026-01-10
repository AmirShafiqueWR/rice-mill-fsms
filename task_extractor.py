"""
FSMS Task Extractor for Rice Export FSMS

Digitalizes documents by extracting "shall" statements and converting
them to operational tasks in the database.

Features:
- Configurable mappings (load from JSON or pass custom)
- Context-aware extraction based on SOP content
- Auto-detection of actors/departments from document
- Fallback inference when mappings don't match
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
CONFIG_FILE = os.getenv("TASK_EXTRACTOR_CONFIG", "task_extractor_config.json")

# Mandatory action keywords (case-insensitive)
MANDATORY_KEYWORDS = [
    r'\bshall\b',
    r'\bmust\b',
    r'\bis required to\b',
    r'\bresponsible for\b',
    r'\bshall be\b',
    r'\bmust be\b'
]

# Default Actor to Department mapping (can be overridden)
DEFAULT_ACTOR_DEPARTMENT_MAP = {
    # Milling Department
    "miller": ("Milling", "Operator"),
    "operator": ("Milling", "Operator"),
    "machine operator": ("Milling", "Machine Operator"),
    "milling supervisor": ("Milling", "Shift Supervisor"),
    "milling team": ("Milling", "Operator"),

    # Quality Department
    "inspector": ("Quality", "Inspector"),
    "quality inspector": ("Quality", "QA Inspector"),
    "qa inspector": ("Quality", "QA Inspector"),
    "qc inspector": ("Quality", "QC Inspector"),
    "quality team": ("Quality", "Inspector"),
    "lab technician": ("Quality", "Lab Technician"),
    "laboratory technician": ("Quality", "Lab Technician"),
    "quality manager": ("Quality", "Quality Manager"),
    "qa": ("Quality", "QA Inspector"),
    "qc": ("Quality", "QC Inspector"),

    # Packaging Department
    "packer": ("Packaging", "Operator"),
    "packaging operator": ("Packaging", "Operator"),
    "packaging supervisor": ("Packaging", "Supervisor"),

    # Storage Department
    "warehouse operator": ("Storage", "Operator"),
    "storage supervisor": ("Storage", "Supervisor"),
    "store keeper": ("Storage", "Store Keeper"),

    # Exports Department
    "export officer": ("Exports", "Officer"),
    "shipping clerk": ("Exports", "Clerk"),
    "documentation officer": ("Exports", "Documentation Officer"),

    # Maintenance
    "technician": ("Milling", "Maintenance Technician"),
    "maintenance technician": ("Milling", "Maintenance Technician"),
    "engineer": ("Milling", "Engineer"),
    "maintenance team": ("Milling", "Maintenance Technician"),

    # Management
    "manager": ("Quality", "Department Manager"),
    "supervisor": ("Milling", "Shift Supervisor"),
    "management representative": ("Quality", "Management Representative"),
    "mr": ("Quality", "Management Representative"),
    "director": ("Quality", "Director"),
    "fsms team leader": ("Quality", "FSMS Team Leader"),
}

# Default ISO Clause mapping based on keywords
DEFAULT_ISO_CLAUSE_KEYWORDS = {
    "8.5.1": ["control", "prevent", "eliminate", "hazard", "contamination", "ccp", "critical control"],
    "8.5.1.2": ["limit", "threshold", "exceed", "maximum", "minimum", "critical limit", "specification"],
    "8.5.1.3": ["monitor", "check", "measure", "verify", "test", "inspect", "reading"],
    "8.5.1.4": ["corrective", "exceeded", "halt", "stop", "notify", "reject", "deviation", "non-conforming"],
    "7.5.3": ["record", "log", "document", "register", "fill", "complete", "maintain records"],
    "7.1.5.1": ["calibrate", "calibration", "equipment", "instrument", "measuring device"],
    "9.0": ["review", "audit", "evaluate", "assess", "performance", "effectiveness"],
}

# Default Priority keywords
DEFAULT_PRIORITY_KEYWORDS = {
    "Critical": ["immediately", "urgent", "halt", "stop production", "critical", "food safety", "aflatoxin", "pathogen"],
    "High": ["before", "prior to", "must", "every shift", "hourly", "every 2 hours", "every 4 hours"],
    "Medium": ["daily", "weekly", "shall", "required"],
    "Low": ["monthly", "quarterly", "annually", "review", "assess", "periodic"]
}

# Valid departments (from models.py)
VALID_DEPARTMENTS = ["Milling", "Quality", "Exports", "Packaging", "Storage"]


# ============================================================================
# Configuration Management
# ============================================================================

@dataclass
class ExtractorConfig:
    """Configuration for task extraction."""
    actor_department_map: dict = field(default_factory=lambda: DEFAULT_ACTOR_DEPARTMENT_MAP.copy())
    iso_clause_keywords: dict = field(default_factory=lambda: DEFAULT_ISO_CLAUSE_KEYWORDS.copy())
    priority_keywords: dict = field(default_factory=lambda: DEFAULT_PRIORITY_KEYWORDS.copy())
    default_department: str = "Quality"
    default_role: str = "Staff"
    default_iso_clause: str = "8.5.1"
    default_priority: str = "Medium"

    @classmethod
    def from_json(cls, json_path: str) -> "ExtractorConfig":
        """Load configuration from JSON file."""
        with open(json_path, 'r') as f:
            data = json.load(f)

        config = cls()
        if "actor_department_map" in data:
            # Convert list format [dept, role] to tuple
            config.actor_department_map = {
                k: tuple(v) if isinstance(v, list) else v
                for k, v in data["actor_department_map"].items()
            }
        if "iso_clause_keywords" in data:
            config.iso_clause_keywords = data["iso_clause_keywords"]
        if "priority_keywords" in data:
            config.priority_keywords = data["priority_keywords"]
        if "default_department" in data:
            config.default_department = data["default_department"]
        if "default_role" in data:
            config.default_role = data["default_role"]

        return config

    def to_json(self, json_path: str):
        """Save configuration to JSON file."""
        data = {
            "actor_department_map": {
                k: list(v) for k, v in self.actor_department_map.items()
            },
            "iso_clause_keywords": self.iso_clause_keywords,
            "priority_keywords": self.priority_keywords,
            "default_department": self.default_department,
            "default_role": self.default_role,
            "default_iso_clause": self.default_iso_clause,
            "default_priority": self.default_priority
        }
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_actor_mapping(self, actor: str, department: str, role: str):
        """Add a new actor mapping."""
        if department not in VALID_DEPARTMENTS:
            raise ValueError(f"Department must be one of: {VALID_DEPARTMENTS}")
        self.actor_department_map[actor.lower()] = (department, role)

    def add_iso_clause_keywords(self, clause: str, keywords: list[str]):
        """Add or extend ISO clause keywords."""
        if clause in self.iso_clause_keywords:
            self.iso_clause_keywords[clause].extend(keywords)
        else:
            self.iso_clause_keywords[clause] = keywords


def load_config() -> ExtractorConfig:
    """Load configuration from file or return defaults."""
    if Path(CONFIG_FILE).exists():
        try:
            return ExtractorConfig.from_json(CONFIG_FILE)
        except Exception as e:
            print(f"Warning: Could not load config from {CONFIG_FILE}: {e}")
    return ExtractorConfig()


def save_default_config(path: str = "task_extractor_config.json"):
    """Save default configuration to a JSON file for customization."""
    config = ExtractorConfig()
    config.to_json(path)
    print(f"Default configuration saved to {path}")
    return path


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExtractedTask:
    """Represents an extracted task from document."""
    sentence: str
    actor: str = ""
    action: str = ""
    object: str = ""
    frequency: Optional[str] = None
    critical_limit: Optional[str] = None
    iso_clause: str = "8.5.1"
    assigned_department: str = "Quality"
    assigned_role: Optional[str] = None
    priority: str = "Medium"
    page_number: Optional[int] = None
    confidence: float = 1.0  # Confidence score for the extraction
    inferred: bool = False   # True if department/role was inferred, not mapped


@dataclass
class ExtractionResult:
    """Result of task extraction operation."""
    success: bool
    document_id: int
    doc_id: str
    version: str
    total_tasks: int
    tasks_by_department: dict = field(default_factory=dict)
    tasks_by_priority: dict = field(default_factory=dict)
    task_ids: list = field(default_factory=list)
    message: str = ""
    errors: list = field(default_factory=list)
    detected_actors: list = field(default_factory=list)  # Actors found but not mapped
    suggested_mappings: dict = field(default_factory=dict)  # Suggested new mappings


@dataclass
class DocumentContext:
    """Context extracted from document for smart mapping."""
    primary_department: str = "Quality"
    mentioned_departments: list = field(default_factory=list)
    unique_actors: list = field(default_factory=list)
    unmapped_actors: list = field(default_factory=list)
    document_type: str = "SOP"
    has_ccps: bool = False
    has_critical_limits: bool = False


# ============================================================================
# Document Context Analysis
# ============================================================================

def analyze_document_context(text: str, config: ExtractorConfig = None) -> DocumentContext:
    """
    Analyze document to understand its context for smarter extraction.

    Args:
        text: Full document text
        config: Extractor configuration

    Returns:
        DocumentContext with analysis results
    """
    if config is None:
        config = ExtractorConfig()

    context = DocumentContext()
    text_lower = text.lower()

    # Detect document type
    if any(word in text_lower for word in ["policy", "commitment", "shall ensure"]):
        context.document_type = "Policy"
    elif any(word in text_lower for word in ["checklist", "form", "log sheet"]):
        context.document_type = "Record"
    elif any(word in text_lower for word in ["flowchart", "diagram", "process flow"]):
        context.document_type = "Process Flow"
    else:
        context.document_type = "SOP"

    # Detect department focus
    dept_mentions = {dept: len(re.findall(dept.lower(), text_lower)) for dept in VALID_DEPARTMENTS}
    context.mentioned_departments = [d for d, c in dept_mentions.items() if c > 0]
    if dept_mentions:
        context.primary_department = max(dept_mentions, key=dept_mentions.get)

    # Detect if document has CCPs
    context.has_ccps = any(word in text_lower for word in ["ccp", "critical control point", "haccp"])

    # Detect if has critical limits
    context.has_critical_limits = bool(re.search(r'[<>≤≥]=?\s*\d+', text))

    # Find all actors in the document
    actor_pattern = r'(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:shall|must|is required)'
    matches = re.findall(actor_pattern, text_lower)
    context.unique_actors = list(set(matches))

    # Identify unmapped actors
    mapped_actors = set(config.actor_department_map.keys())
    context.unmapped_actors = [
        actor for actor in context.unique_actors
        if not any(mapped in actor for mapped in mapped_actors)
    ]

    return context


def suggest_actor_mappings(context: DocumentContext) -> dict[str, tuple[str, str]]:
    """
    Suggest mappings for unmapped actors based on context.

    Args:
        context: DocumentContext from analysis

    Returns:
        Dict of actor -> (department, role) suggestions
    """
    suggestions = {}

    for actor in context.unmapped_actors:
        actor_lower = actor.lower()

        # Use keyword matching to suggest department
        dept = context.primary_department  # Default to document's primary department
        role = actor.title()  # Use actor name as role

        # Quality-related actors
        if any(word in actor_lower for word in ["quality", "inspector", "qa", "qc", "lab", "test", "analyst"]):
            dept = "Quality"
            if "manager" in actor_lower:
                role = "Quality Manager"
            elif "lab" in actor_lower or "analyst" in actor_lower:
                role = "Lab Technician"
            else:
                role = "Inspector"

        # Milling/Production actors
        elif any(word in actor_lower for word in ["operator", "miller", "machine", "production", "process"]):
            dept = "Milling"
            if "supervisor" in actor_lower:
                role = "Shift Supervisor"
            else:
                role = "Operator"

        # Packaging actors
        elif any(word in actor_lower for word in ["pack", "packaging", "bag", "seal"]):
            dept = "Packaging"
            role = "Operator"

        # Storage actors
        elif any(word in actor_lower for word in ["warehouse", "storage", "store", "inventory"]):
            dept = "Storage"
            role = "Operator"

        # Export actors
        elif any(word in actor_lower for word in ["export", "ship", "document", "customs"]):
            dept = "Exports"
            role = "Officer"

        # Maintenance actors
        elif any(word in actor_lower for word in ["maintenance", "technician", "mechanic", "engineer"]):
            dept = "Milling"
            role = "Maintenance Technician"

        # Management actors
        elif any(word in actor_lower for word in ["manager", "director", "supervisor", "head", "lead"]):
            dept = "Quality"  # Default management to Quality for FSMS
            role = "Manager"

        suggestions[actor] = (dept, role)

    return suggestions


# ============================================================================
# Text Extraction Patterns
# ============================================================================

def extract_mandatory_sentences(text: str) -> list[tuple[str, int]]:
    """
    Extract sentences containing mandatory action keywords.

    Args:
        text: Document text

    Returns:
        List of (sentence, approximate_page) tuples
    """
    sentences = []

    # Build combined pattern for mandatory keywords
    keyword_pattern = '|'.join(MANDATORY_KEYWORDS)

    # Split text into pages (approximate by page breaks or character count)
    pages = text.split('\f')  # Form feed is common page separator
    if len(pages) == 1:
        # No page breaks, estimate by character count (~3000 chars per page)
        char_per_page = 3000
        pages = [text[i:i+char_per_page] for i in range(0, len(text), char_per_page)]

    for page_num, page_text in enumerate(pages, 1):
        # Extract sentences containing mandatory keywords
        # Pattern: Capital letter to period, containing keyword
        sentence_pattern = r'([A-Z][^.]*(?:' + keyword_pattern + r')[^.]*\.)'

        matches = re.findall(sentence_pattern, page_text, re.IGNORECASE)

        for match in matches:
            # Clean up the sentence
            sentence = ' '.join(match.split())
            if len(sentence) > 20:  # Filter out too short matches
                sentences.append((sentence, page_num))

    return sentences


# ============================================================================
# Semantic Parsing with Context
# ============================================================================

def extract_actor(
    sentence: str,
    config: ExtractorConfig = None,
    context: DocumentContext = None
) -> tuple[str, str, str, bool]:
    """
    Extract actor from sentence and map to department/role.

    Args:
        sentence: Task sentence
        config: Extractor configuration
        context: Document context for fallback inference

    Returns:
        Tuple of (actor, department, role, inferred)
        inferred=True if mapping was guessed, not from config
    """
    if config is None:
        config = ExtractorConfig()

    sentence_lower = sentence.lower()

    # Find actor before "shall" or "must"
    actor_match = re.search(r'(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:shall|must|is required)', sentence_lower)

    if actor_match:
        actor = actor_match.group(1).strip()

        # Check actor mapping in config
        for key, (dept, role) in config.actor_department_map.items():
            if key in actor:
                return actor, dept, role, False

        # Fallback: Infer from keywords in actor name
        inferred_dept = config.default_department
        inferred_role = config.default_role

        if any(word in actor for word in ["quality", "inspector", "qa", "qc", "lab"]):
            inferred_dept, inferred_role = "Quality", "Inspector"
        elif any(word in actor for word in ["operator", "miller", "machine"]):
            inferred_dept, inferred_role = "Milling", "Operator"
        elif any(word in actor for word in ["packer", "packaging"]):
            inferred_dept, inferred_role = "Packaging", "Operator"
        elif any(word in actor for word in ["warehouse", "storage", "store"]):
            inferred_dept, inferred_role = "Storage", "Operator"
        elif any(word in actor for word in ["export", "shipping"]):
            inferred_dept, inferred_role = "Exports", "Officer"
        elif context and context.primary_department:
            # Use document's primary department as fallback
            inferred_dept = context.primary_department
            inferred_role = actor.title()

        return actor, inferred_dept, inferred_role, True

    return "staff", config.default_department, config.default_role, True


def extract_action(sentence: str) -> str:
    """
    Extract action verb from sentence.

    Args:
        sentence: Task sentence

    Returns:
        Action verb
    """
    # Pattern: verb immediately after shall/must
    action_match = re.search(
        r'(?:shall|must|is required to|responsible for)\s+(?:be\s+)?(\w+)',
        sentence,
        re.IGNORECASE
    )

    if action_match:
        action = action_match.group(1).lower()
        # Filter out common non-action words
        if action not in ["the", "a", "an", "that", "this", "all"]:
            return action

    return "perform"


def extract_object(sentence: str) -> str:
    """
    Extract object of the action from sentence.

    Args:
        sentence: Task sentence

    Returns:
        Object phrase
    """
    # Pattern: noun phrase after action verb
    object_match = re.search(
        r'(?:shall|must)\s+(?:be\s+)?\w+(?:ed|ing)?\s+(?:the\s+)?([^,\.]+?)(?:\s+(?:every|before|after|at|in|on|using|with|to ensure|if|when|prior)|[,\.])',
        sentence,
        re.IGNORECASE
    )

    if object_match:
        obj = object_match.group(1).strip()
        # Clean up
        obj = re.sub(r'^(the|a|an)\s+', '', obj, flags=re.IGNORECASE)
        return obj[:100]  # Limit length

    # Fallback: extract noun phrase after verb
    fallback_match = re.search(
        r'(?:shall|must)\s+\w+\s+(.+?)(?:\.|,|every|before|after|using)',
        sentence,
        re.IGNORECASE
    )

    if fallback_match:
        return fallback_match.group(1).strip()[:100]

    return "task requirements"


def extract_frequency(sentence: str) -> Optional[str]:
    """
    Extract frequency/timing from sentence.

    Args:
        sentence: Task sentence

    Returns:
        Frequency string or None
    """
    sentence_lower = sentence.lower()

    # Specific frequency patterns
    patterns = [
        (r'every\s+(\d+)\s*hours?', lambda m: f"Every {m.group(1)} hours"),
        (r'every\s+(\d+)\s*minutes?', lambda m: f"Every {m.group(1)} minutes"),
        (r'every\s+shift', lambda m: "Every shift"),
        (r'per\s+shift', lambda m: "Per shift"),
        (r'per\s+batch', lambda m: "Per batch"),
        (r'each\s+batch', lambda m: "Each batch"),
        (r'before\s+each\s+(\w+)', lambda m: f"Before each {m.group(1)}"),
        (r'after\s+each\s+(\w+)', lambda m: f"After each {m.group(1)}"),
        (r'at\s+the\s+start\s+of\s+(\w+)', lambda m: f"At start of {m.group(1)}"),
        (r'at\s+the\s+end\s+of\s+(\w+)', lambda m: f"At end of {m.group(1)}"),
        (r'\bdaily\b', lambda m: "Daily"),
        (r'\bweekly\b', lambda m: "Weekly"),
        (r'\bmonthly\b', lambda m: "Monthly"),
        (r'\bhourly\b', lambda m: "Hourly"),
        (r'once\s+per\s+(\w+)', lambda m: f"Once per {m.group(1)}"),
        (r'twice\s+per\s+(\w+)', lambda m: f"Twice per {m.group(1)}"),
        (r'continuously', lambda m: "Continuous"),
        (r'as\s+needed', lambda m: "As needed"),
        (r'when\s+required', lambda m: "When required"),
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, sentence_lower)
        if match:
            return formatter(match)

    return None


def extract_critical_limit(sentence: str) -> Optional[str]:
    """
    Extract critical limits/thresholds from sentence.

    Args:
        sentence: Task sentence

    Returns:
        Critical limit string or None
    """
    limits = []

    # Temperature patterns
    temp_match = re.search(r'([<>≤≥]=?\s*\d+\.?\d*\s*°?[CF])', sentence)
    if temp_match:
        limits.append(temp_match.group(1))

    # Percentage patterns
    pct_match = re.search(r'([<>≤≥]=?\s*\d+\.?\d*\s*%)', sentence)
    if pct_match:
        limits.append(pct_match.group(1))

    # PPB/PPM patterns
    ppb_match = re.search(r'(\d+\.?\d*\s*(?:ppb|ppm))', sentence, re.IGNORECASE)
    if ppb_match:
        limits.append(ppb_match.group(1))

    # Max/Min patterns
    max_min_match = re.search(r'((?:max(?:imum)?|min(?:imum)?)\s*:?\s*\d+\.?\d*\s*\w*)', sentence, re.IGNORECASE)
    if max_min_match:
        limits.append(max_min_match.group(1))

    # Weight patterns
    weight_match = re.search(r'(\d+\.?\d*\s*(?:kg|g|mg|pounds?|lbs?))', sentence, re.IGNORECASE)
    if weight_match:
        limits.append(weight_match.group(1))

    # Time duration patterns
    time_match = re.search(r'within\s+(\d+\s*(?:hours?|minutes?|seconds?))', sentence, re.IGNORECASE)
    if time_match:
        limits.append(f"within {time_match.group(1)}")

    if limits:
        return ", ".join(limits)

    return None


def determine_iso_clause(
    sentence: str,
    has_critical_limit: bool,
    has_frequency: bool,
    config: ExtractorConfig = None
) -> str:
    """
    Determine ISO clause based on sentence content.

    Args:
        sentence: Task sentence
        has_critical_limit: Whether critical limit was extracted
        has_frequency: Whether frequency was extracted
        config: Extractor configuration

    Returns:
        ISO clause string
    """
    if config is None:
        config = ExtractorConfig()

    sentence_lower = sentence.lower()

    # Check each clause's keywords
    for clause, keywords in config.iso_clause_keywords.items():
        if any(kw in sentence_lower for kw in keywords):
            # Special handling for 8.5.1.2 (needs critical limit)
            if clause == "8.5.1.2" and has_critical_limit:
                return clause
            elif clause == "8.5.1.3" and has_frequency:
                return clause
            elif clause not in ["8.5.1.2", "8.5.1.3"]:
                return clause

    # Default based on extracted data
    if has_critical_limit:
        return "8.5.1.2"
    elif has_frequency:
        return "8.5.1.3"

    return config.default_iso_clause


def determine_priority(
    sentence: str,
    iso_clause: str,
    has_critical_limit: bool,
    config: ExtractorConfig = None
) -> str:
    """
    Determine task priority based on content.

    Args:
        sentence: Task sentence
        iso_clause: Assigned ISO clause
        has_critical_limit: Whether has critical limit
        config: Extractor configuration

    Returns:
        Priority string
    """
    if config is None:
        config = ExtractorConfig()

    sentence_lower = sentence.lower()

    # Critical priority checks
    if has_critical_limit and iso_clause == "8.5.1.2":
        return "Critical"

    for keyword in config.priority_keywords.get("Critical", []):
        if keyword in sentence_lower:
            return "Critical"

    # High priority checks
    if iso_clause == "8.5.1":
        return "High"

    for keyword in config.priority_keywords.get("High", []):
        if keyword in sentence_lower:
            return "High"

    # Low priority checks
    for keyword in config.priority_keywords.get("Low", []):
        if keyword in sentence_lower:
            return "Low"

    return config.default_priority


# ============================================================================
# Main Extraction Function
# ============================================================================

def parse_task_from_sentence(
    sentence: str,
    page_number: int = None,
    config: ExtractorConfig = None,
    context: DocumentContext = None
) -> ExtractedTask:
    """
    Parse a single sentence into an ExtractedTask.

    Args:
        sentence: Mandatory action sentence
        page_number: Page number where found
        config: Extractor configuration
        context: Document context for smart mapping

    Returns:
        ExtractedTask object
    """
    if config is None:
        config = ExtractorConfig()

    actor, department, role, inferred = extract_actor(sentence, config, context)
    action = extract_action(sentence)
    obj = extract_object(sentence)
    frequency = extract_frequency(sentence)
    critical_limit = extract_critical_limit(sentence)
    iso_clause = determine_iso_clause(sentence, critical_limit is not None, frequency is not None, config)
    priority = determine_priority(sentence, iso_clause, critical_limit is not None, config)

    # Calculate confidence score
    confidence = 1.0 if not inferred else 0.7

    return ExtractedTask(
        sentence=sentence,
        actor=actor,
        action=action,
        object=obj,
        frequency=frequency,
        critical_limit=critical_limit,
        iso_clause=iso_clause,
        assigned_department=department,
        assigned_role=role,
        priority=priority,
        page_number=page_number,
        confidence=confidence,
        inferred=inferred
    )


def extract_tasks_from_text(
    text: str,
    config: ExtractorConfig = None,
    analyze_context: bool = True
) -> tuple[list[ExtractedTask], DocumentContext]:
    """
    Extract all tasks from document text.

    Args:
        text: Full document text
        config: Extractor configuration (uses default if None)
        analyze_context: Whether to analyze document context first

    Returns:
        Tuple of (List of ExtractedTask objects, DocumentContext)
    """
    if config is None:
        config = load_config()

    # Analyze document context
    context = None
    if analyze_context:
        context = analyze_document_context(text, config)

    sentences = extract_mandatory_sentences(text)
    tasks = []

    for sentence, page_num in sentences:
        task = parse_task_from_sentence(sentence, page_num, config, context)
        tasks.append(task)

    return tasks, context


# ============================================================================
# API Integration
# ============================================================================

async def get_document_by_doc_id(doc_id: str) -> dict:
    """
    Fetch document by doc_id.

    Args:
        doc_id: Document ID (e.g., FSMS-SOP-001)

    Returns:
        Document data
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/documents",
            params={"limit": 100}
        )
        response.raise_for_status()
        documents = response.json()["documents"]

        for doc in documents:
            if doc.get("doc_id") == doc_id:
                return doc

        raise ValueError(f"Document with doc_id '{doc_id}' not found")


async def get_existing_tasks(document_id: int, version: str) -> list:
    """
    Check for existing tasks for a document version.

    Args:
        document_id: Database ID
        version: Document version

    Returns:
        List of existing tasks
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/tasks",
            params={"document_id": document_id}
        )
        response.raise_for_status()
        tasks = response.json()

        # Filter by version
        return [t for t in tasks if t.get("source_document_version") == version]


async def create_tasks_bulk(tasks: list[dict]) -> dict:
    """
    Create tasks in bulk via API.

    Args:
        tasks: List of task dictionaries

    Returns:
        API response
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/tasks",
            json={"tasks": tasks}
        )
        response.raise_for_status()
        return response.json()


async def extract_and_create_tasks(
    doc_id: str,
    text: str,
    config: ExtractorConfig = None,
    skip_if_exists: bool = True,
    auto_add_mappings: bool = False
) -> ExtractionResult:
    """
    Main function to extract tasks from text and create in database.

    Args:
        doc_id: Document ID
        text: Document text content
        config: Custom extractor configuration
        skip_if_exists: Skip if tasks already exist for this version
        auto_add_mappings: Automatically add suggested mappings to config

    Returns:
        ExtractionResult with summary
    """
    if config is None:
        config = load_config()

    try:
        # Get document from API
        document = await get_document_by_doc_id(doc_id)
        document_id = document["id"]
        version = document.get("version", "v1.0")
        status = document.get("status", "")

        # Verify document is Controlled
        if status != "Controlled":
            return ExtractionResult(
                success=False,
                document_id=document_id,
                doc_id=doc_id,
                version=version,
                total_tasks=0,
                message=f"Document must be Controlled status (current: {status})",
                errors=["Only extract tasks from Controlled documents"]
            )

        # Check for existing tasks
        if skip_if_exists:
            existing = await get_existing_tasks(document_id, version)
            if existing:
                return ExtractionResult(
                    success=True,
                    document_id=document_id,
                    doc_id=doc_id,
                    version=version,
                    total_tasks=len(existing),
                    message=f"Tasks already extracted for {doc_id} {version} ({len(existing)} tasks exist)"
                )

        # Extract tasks from text with context analysis
        extracted_tasks, context = extract_tasks_from_text(text, config, analyze_context=True)

        # Get suggested mappings for unmapped actors
        suggested_mappings = {}
        if context and context.unmapped_actors:
            suggested_mappings = suggest_actor_mappings(context)

            if auto_add_mappings:
                for actor, (dept, role) in suggested_mappings.items():
                    config.add_actor_mapping(actor, dept, role)
                # Re-extract with new mappings
                extracted_tasks, context = extract_tasks_from_text(text, config, analyze_context=False)

        if not extracted_tasks:
            return ExtractionResult(
                success=True,
                document_id=document_id,
                doc_id=doc_id,
                version=version,
                total_tasks=0,
                message="No mandatory action statements found in document",
                detected_actors=context.unique_actors if context else [],
                suggested_mappings=suggested_mappings
            )

        # Convert to API format
        api_tasks = []
        for task in extracted_tasks:
            api_tasks.append({
                "document_id": document_id,
                "task_description": task.sentence,
                "action": task.action,
                "object": task.object,
                "iso_clause": task.iso_clause,
                "critical_limit": task.critical_limit,
                "frequency": task.frequency,
                "assigned_department": task.assigned_department,
                "assigned_role": task.assigned_role,
                "priority": task.priority,
                "status": "Pending",
                "source_document_version": version,
                "extracted_from_page": task.page_number
            })

        # Create tasks via API
        result = await create_tasks_bulk(api_tasks)

        # Build summary
        tasks_by_dept = {}
        tasks_by_priority = {}
        inferred_count = 0

        for task in extracted_tasks:
            dept = task.assigned_department
            priority = task.priority

            if task.inferred:
                inferred_count += 1

            if dept not in tasks_by_dept:
                tasks_by_dept[dept] = {"total": 0, "by_priority": {}}
            tasks_by_dept[dept]["total"] += 1
            tasks_by_dept[dept]["by_priority"][priority] = \
                tasks_by_dept[dept]["by_priority"].get(priority, 0) + 1

            tasks_by_priority[priority] = tasks_by_priority.get(priority, 0) + 1

        message = f"Successfully extracted {len(api_tasks)} tasks from {doc_id} {version}"
        if inferred_count > 0:
            message += f" ({inferred_count} with inferred mappings)"

        return ExtractionResult(
            success=True,
            document_id=document_id,
            doc_id=doc_id,
            version=version,
            total_tasks=result.get("created_count", len(api_tasks)),
            tasks_by_department=tasks_by_dept,
            tasks_by_priority=tasks_by_priority,
            task_ids=result.get("task_ids", []),
            message=message,
            detected_actors=context.unique_actors if context else [],
            suggested_mappings=suggested_mappings
        )

    except Exception as e:
        return ExtractionResult(
            success=False,
            document_id=0,
            doc_id=doc_id,
            version="",
            total_tasks=0,
            message=f"Extraction failed: {str(e)}",
            errors=[str(e)]
        )


# ============================================================================
# Report Generation
# ============================================================================

def generate_extraction_report(result: ExtractionResult) -> str:
    """
    Generate human-readable extraction report.

    Args:
        result: ExtractionResult object

    Returns:
        Formatted report string
    """
    if not result.success:
        return f"""Extraction Failed

Document: {result.doc_id}
Error: {result.message}
Details: {', '.join(result.errors) if result.errors else 'N/A'}
"""

    if result.total_tasks == 0:
        report = f"""No Tasks Extracted

Document: {result.doc_id} {result.version}
Reason: {result.message}
"""
        if result.detected_actors:
            report += f"\nActors found in document: {', '.join(result.detected_actors)}"
        if result.suggested_mappings:
            report += "\n\nSuggested mappings for unmapped actors:"
            for actor, (dept, role) in result.suggested_mappings.items():
                report += f"\n  '{actor}' -> ({dept}, {role})"
        return report

    report = f"""Extracted {result.total_tasks} tasks from {result.doc_id} {result.version}

Tasks by Department:
"""

    for dept, data in result.tasks_by_department.items():
        priority_str = ", ".join(f"{count} {p}" for p, count in data["by_priority"].items())
        report += f"- {dept}: {data['total']} tasks ({priority_str})\n"

    report += "\nPriority Breakdown:\n"
    for priority in ["Critical", "High", "Medium", "Low"]:
        count = result.tasks_by_priority.get(priority, 0)
        if count > 0:
            report += f"- {priority}: {count} tasks\n"

    report += f"\nAll tasks saved to database. Document ID: {result.document_id}"

    # Add suggestions if there are unmapped actors
    if result.suggested_mappings:
        report += "\n\nNote: Some actors were not in the mapping config."
        report += "\nSuggested mappings (add to task_extractor_config.json):"
        for actor, (dept, role) in result.suggested_mappings.items():
            report += f"\n  \"{actor}\": [\"{dept}\", \"{role}\"]"

    return report


# ============================================================================
# Utility Functions
# ============================================================================

def preview_extraction(text: str, config: ExtractorConfig = None) -> str:
    """
    Preview extraction without creating tasks in database.
    Useful for testing and validation.

    Args:
        text: Document text
        config: Extractor configuration

    Returns:
        Preview report string
    """
    tasks, context = extract_tasks_from_text(text, config)

    report = f"""Extraction Preview

Document Context:
- Type: {context.document_type if context else 'Unknown'}
- Primary Department: {context.primary_department if context else 'Unknown'}
- Has CCPs: {context.has_ccps if context else False}
- Has Critical Limits: {context.has_critical_limits if context else False}

Actors Found: {', '.join(context.unique_actors) if context else 'None'}
Unmapped Actors: {', '.join(context.unmapped_actors) if context else 'None'}

Extracted {len(tasks)} Tasks:
"""

    for i, task in enumerate(tasks, 1):
        inferred_marker = " [INFERRED]" if task.inferred else ""
        report += f"""
{i}. {task.sentence[:80]}{'...' if len(task.sentence) > 80 else ''}
   Actor: {task.actor} -> {task.assigned_department}/{task.assigned_role}{inferred_marker}
   Action: {task.action}
   Object: {task.object}
   Frequency: {task.frequency or 'Not specified'}
   Critical Limit: {task.critical_limit or 'None'}
   ISO Clause: {task.iso_clause}
   Priority: {task.priority}
   Confidence: {task.confidence:.0%}
"""

    if context and context.unmapped_actors:
        suggestions = suggest_actor_mappings(context)
        report += "\nSuggested Mappings for Unmapped Actors:"
        for actor, (dept, role) in suggestions.items():
            report += f"\n  '{actor}' -> ({dept}, {role})"

    return report
