"""Notice extraction module for converting free-text placement notices to structured Facts.

This module uses LLM to extract eligibility criteria from unstructured notices while detecting
corrections, updates, and deadline extensions. Implements extraction logic per DESIGN.md §3.2.

Key responsibilities:
1. Parse free-text notices into structured Fact objects
2. Detect supersession markers ("Correction:", "Update:", "Deadline extended")
3. Extract confidence scores for uncertain criteria
4. Handle ambiguous or incomplete notices gracefully

The LLM is used ONLY for extraction and supersession detection - never for eligibility decisions.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from core.schemas import SourceType, SOURCE_AUTHORITY_RANK
from database.models import Fact as FactModel, utcnow
from extraction.llm_client import LLMClient, get_llm_client


# Branch normalization mappings
# Maps various branch name formats to standardized codes
BRANCH_ALIASES: dict[str, str] = {
    # Computer Science and Engineering
    "computer science and engineering": "CSE",
    "computer science": "CSE",
    "cs": "CSE",
    "cse": "CSE",
    
    # Information Science and Engineering
    "information science and engineering": "ISE",
    "information science": "ISE",
    "is": "ISE",
    "ise": "ISE",
    
    # CSE AI & ML
    "cse ai&ml": "CSE(AI&ML)",
    "cse aiml": "CSE(AI&ML)",
    "cse (ai&ml)": "CSE(AI&ML)",
    "cse (aiml)": "CSE(AI&ML)",
    "ai&ml": "CSE(AI&ML)",
    "aiml": "CSE(AI&ML)",
    "ci": "CSE(AI&ML)",
    "artificial intelligence and machine learning": "CSE(AI&ML)",
    
    # CSE Cyber Security
    "cse cyber security": "Cybersecurity",
    "cse cybersecurity": "Cybersecurity",
    "cyber security": "Cybersecurity",
    "cybersecurity": "Cybersecurity",
    "cy": "Cybersecurity",
    
    # Electronics and Communication Engineering
    "electronics and communication engineering": "ECE",
    "electronics and communication": "ECE",
    "ec": "ECE",
    "ece": "ECE",
    
    # Mechanical Engineering
    "mechanical engineering": "MECH",
    "mechanical": "MECH",
    "me": "MECH",
    "mech": "MECH",
    
    # Electronics and Telecommunication Engineering
    "electronics and telecommunication engineering": "ETE",
    "electronics and telecommunication": "ETE",
    "et": "ETE",
    "ete": "ETE",
    
    # Electronics and Instrumentation Engineering
    "electronics and instrumentation engineering": "EIE",
    "electronics and instrumentation": "EIE",
    "ei": "EIE",
    "eie": "EIE",
    
    # Information Technology (common alternative) - map to ISE
    "information technology": "ISE",
    "it": "ISE",
}

# Branch group expansions for "allied branches"
BRANCH_GROUPS: dict[str, list[str]] = {
    "cs allied": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"],
    "cs allied branches": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"],
    "cse allied": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"],
    "cse allied branches": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"],
    "ece allied": ["ECE", "ETE", "EIE"],
    "ece allied branches": ["ECE", "ETE", "EIE"],
    "ec allied": ["ECE", "ETE", "EIE"],
    "ec allied branches": ["ECE", "ETE", "EIE"],
}


# Extraction prompt template
EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting structured eligibility criteria from placement notices.

Your task is to extract ALL eligibility requirements from notices sent by placement cells, coordinators, 
or students about company recruitment drives.

CRITICAL: Use EXACT criterion type names as listed below. Do NOT use variations.

Required criterion types (use EXACTLY as written):
- min_cgpa: Minimum CGPA requirement (e.g., "7.5 CGPA required")
- max_backlogs: Maximum allowed backlogs (e.g., "no active backlogs", "max 2 backlogs")
- allowed_branches: Branch restrictions (e.g., "CSE/ISE only", "open to all branches")
- branch: Alternative for allowed_branches
- min_10th_pct: Minimum 10th percentage (use "min_10th_pct", NOT "min_tenth_pct")
- min_12th_pct: Minimum 12th percentage (use "min_12th_pct", NOT "min_twelfth_pct")
- no_prior_offer: Prior offer restrictions (e.g., "students with offers cannot apply")
- deadline: Registration deadline (MUST be in ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- registration_link: The URL students use to register/apply (e.g., "Link to apply: https://...",
  "Register here: https://forms.gle/...", "🔗 Fill out form: https://..."). Extract the URL exactly
  as written, with operator "eq". This is informational, not an eligibility rule — extract it
  whenever a notice contains an application/registration URL, even if the rest of the notice has
  no other extractable criteria.

NAMING RULES - VERY IMPORTANT:
✓ CORRECT: min_10th_pct, min_12th_pct
✗ WRONG: min_tenth_pct, min_twelfth_pct, tenth_pct, twelfth_pct

BRANCH EXTRACTION RULES - CRITICAL:
1. Extract branches as a comma-separated list of individual branch codes
2. Use standard codes: CSE, ISE, CSE(AI&ML), Cybersecurity, ECE, MECH, ETE, EIE, IT
3. NEVER extract group names like "CS Allied" or "ECE Allied" - these will be expanded automatically
4. For compound statements like "CSE, ISE and allied branches", extract: "CSE,ISE,CSE(AI&ML),Cybersecurity"
5. Common expansions:
   - "CS Allied" or "CSE Allied" → CSE, ISE, CSE(AI&ML), Cybersecurity
   - "ECE Allied" or "EC Allied" → ECE, ETE, EIE
6. Examples:
   - "CSE and ISE only" → "CSE,ISE"
   - "CS Allied branches" → "CSE,ISE,CSE(AI&ML),Cybersecurity"
   - "ECE, ETE, EIE" → "ECE,ETE,EIE"
   - "All branches" → "ALL"

ALLOWED_BRANCHES LIST_OPERATION - CRITICAL (allowed_branches criterion ONLY):
Every allowed_branches criterion MUST include a "list_operation" field: "add", "remove", or "replace".
- Use "add" when the notice is EXTENDING eligibility to additional branch(es) on top of whatever
  is already eligible — phrasing like "can also apply", "is/are now also eligible", "added to the
  allowed branches", "X branch has been included". Extract ONLY the newly-added branch(es) as the
  value, with operator "in" — do NOT guess or repeat branches from earlier notices you haven't seen.
- Use "remove" when the notice REVOKES eligibility for specific branch(es) that were previously
  eligible, without stating what the new complete list is — phrasing like "X cannot apply", "X is/are
  no longer eligible", "X branch has been removed/excluded". Extract ONLY the branch(es) being removed
  as the value, with operator "in" (NOT "not_in" — leave turning this into an exclusion rule to the
  system; your job is just to say which branch(es) lost eligibility in THIS notice).
- Use "replace" (the default) when the notice states the complete, final set of eligible branches
  (or explicitly uses "only"/"restricted to" to give the full final set), or there is no reference to
  a prior state at all. For "replace", choose operator "in" for an inclusive list or "not_in" for an
  explicit exclusion list, as before.
Examples:
   - "ECE branch can also apply to Schneider Electric" → {"criterion_type": "allowed_branches", "operator": "in", "value": "ECE", "list_operation": "add", ...}
   - "MECH students are now also eligible" → {"criterion_type": "allowed_branches", "operator": "in", "value": "MECH", "list_operation": "add", ...}
   - "CSE branch cannot apply to Schneider Electric" → {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE", "list_operation": "remove", ...}
   - "ECE students are no longer eligible" → {"criterion_type": "allowed_branches", "operator": "in", "value": "ECE", "list_operation": "remove", ...}
   - "Only CSE and ISE are eligible for this drive" → {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE,ISE", "list_operation": "replace", ...}
   - "CS Allied branches" (first-time criterion for a drive) → {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE,ISE,CSE(AI&ML),Cybersecurity", "list_operation": "replace", ...}

DEADLINE EXTRACTION RULES - CRITICAL:
1. ALWAYS extract deadline in ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
2. Convert relative dates to absolute dates (use context to infer year if needed)
3. Examples:
   - "Apply by Nov 5th" → "2024-11-05"
   - "Deadline: 5th November 6 PM" → "2024-11-05T18:00:00"
   - "Register before 15/11/2024" → "2024-11-15"
4. If time is mentioned, include it with T separator
5. If only date is mentioned, use YYYY-MM-DD format

Supersession detection:
- Look for phrases like "Correction:", "Update:", "Deadline extended", "Change:", "Revised:"
- If found, mark is_correction=true and try to identify what notice is being corrected
- Common patterns: "Correction: CGPA is 7.5 not 7.0", "Deadline extended to 6PM from 4PM"

IMPORTANT RULES:
1. Extract ONLY information explicitly stated in the notice
2. Do NOT infer or assume criteria not mentioned
3. If something is ambiguous, mark confidence as "low" and include a note
4. For operators: use "gte" (>=), "lte" (<=), "eq" (=), "in" (list membership), "not_in" (exclusion)
5. Return empty list if no criteria can be extracted
6. For numeric values, extract just the number
7. ALWAYS use underscore format with numbers: min_10th_pct, min_12th_pct

Output format: JSON array of criterion objects with this structure:
{
  "criterion_type": "min_cgpa",
  "operator": "gte",
  "value": "7.5",
  "scope": "ALL",
  "confidence": "high",
  "is_correction": false,
  "supersedes_ref": null,
  "notes": ""
}
For "criterion_type": "allowed_branches" ONLY, also include "list_operation": "add", "remove", or
"replace" per the ALLOWED_BRANCHES LIST_OPERATION rules above.

EXAMPLE outputs:
- For "Link to apply: https://forms.gle/abc123": {"criterion_type": "registration_link", "operator": "eq", "value": "https://forms.gle/abc123", ...}
- For "70% in 12th": {"criterion_type": "min_12th_pct", "operator": "gte", "value": "70", ...}
- For "60% in 10th": {"criterion_type": "min_10th_pct", "operator": "gte", "value": "60", ...}
- For "CSE and ISE only": {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE,ISE", "list_operation": "replace", ...}
- For "CS Allied branches": {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE,ISE,CSE(AI&ML),Cybersecurity", "list_operation": "replace", ...}
- For "ECE branch can also apply": {"criterion_type": "allowed_branches", "operator": "in", "value": "ECE", "list_operation": "add", ...}
- For "CSE branch cannot apply": {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE", "list_operation": "remove", ...}
- For "Deadline: Nov 5th 6PM": {"criterion_type": "deadline", "operator": "lte", "value": "2024-11-05T18:00:00", ...}
"""


EXTRACTION_USER_PROMPT_TEMPLATE = """Extract eligibility criteria from this notice:

NOTICE TEXT:
{notice_text}

CONTEXT:
- Source: {source_type}
- Message ID: {message_id}
- Timestamp: {timestamp}

Extract all criteria following the rules provided. Return JSON array.
"""


# Confidence levels ranked so threshold filtering can compare numerically.
# Higher number = higher confidence. Unknown/missing confidence defaults to medium.
CONFIDENCE_RANK: dict[str, int] = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


# Mapping of common incorrect criterion type names to correct ones
# This ensures consistency even if LLM uses variations
CRITERION_TYPE_ALIASES: dict[str, str] = {
    'min_tenth_pct': 'min_10th_pct',
    'min_twelfth_pct': 'min_12th_pct',
    'tenth_pct': 'min_10th_pct',
    'twelfth_pct': 'min_12th_pct',
    'tenth_percentage': 'min_10th_pct',
    'twelfth_percentage': 'min_12th_pct',
    'branch': 'allowed_branches',
    'apply_link': 'registration_link',
    'application_link': 'registration_link',
    'registration_url': 'registration_link',
    'apply_url': 'registration_link',
    'link_to_apply': 'registration_link',
}


def normalize_branch_value(value: Any) -> Any:
    """Normalize branch values by expanding group names and standardizing codes.
    
    Args:
        value: Branch value (could be string, list, or already normalized)
        
    Returns:
        Normalized value (expanded and standardized)
    """
    # If it's already a list, process each item
    if isinstance(value, list):
        normalized_branches = []
        for branch in value:
            normalized_branches.extend(_normalize_single_branch_value(branch))
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for b in normalized_branches:
            if b not in seen:
                seen.add(b)
                result.append(b)
        return result
    
    # If it's a string, split by comma and process
    if isinstance(value, str):
        # Special case: "ALL" or "all branches"
        if value.strip().upper() == "ALL" or value.strip().lower() == "all branches":
            return "ALL"
        
        # Split by comma or slash
        parts = [p.strip() for p in value.replace('/', ',').split(',')]
        normalized_branches = []
        for part in parts:
            normalized_branches.extend(_normalize_single_branch_value(part))
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for b in normalized_branches:
            if b not in seen:
                seen.add(b)
                result.append(b)
        
        return result
    
    # Return as-is if not string or list
    return value


def _normalize_single_branch_value(branch_str: str) -> list[str]:
    """Normalize a single branch string to standard codes.
    
    Args:
        branch_str: Branch name/code (e.g., "CS", "CS Allied", "Computer Science")
        
    Returns:
        List of normalized branch codes
    """
    branch_lower = branch_str.strip().lower()
    
    # Check if it's a group name (like "CS Allied")
    if branch_lower in BRANCH_GROUPS:
        return BRANCH_GROUPS[branch_lower]
    
    # Check if it's an alias
    if branch_lower in BRANCH_ALIASES:
        return [BRANCH_ALIASES[branch_lower]]
    
    # If not found in mappings, return original (might be already correct)
    return [branch_str.strip()]


def normalize_deadline_value(value: Any) -> str:
    """Normalize deadline value to ISO 8601 format.
    
    Args:
        value: Deadline value (various formats)
        
    Returns:
        ISO 8601 formatted string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    """
    if not isinstance(value, str):
        return str(value)
    
    value_str = value.strip()
    
    # If already in ISO format, return as-is
    if 'T' in value_str or len(value_str) == 10 and value_str.count('-') == 2:
        return value_str
    
    # Try to parse various formats
    from dateutil import parser as date_parser
    
    try:
        parsed_date = date_parser.parse(value_str, fuzzy=True)
        
        # If time component is midnight, return just date
        if parsed_date.hour == 0 and parsed_date.minute == 0 and parsed_date.second == 0:
            return parsed_date.strftime("%Y-%m-%d")
        else:
            return parsed_date.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        # If parsing fails, return original
        return value_str


def extract_criteria_from_notice(
    notice_text: str,
    source_id: str,
    source_type: SourceType,
    timestamp: datetime,
    drive_id: str,
    llm_client: LLMClient | None = None,
) -> list[FactModel]:
    """Extract structured criteria from a free-text placement notice.
    
    Uses LLM to parse unstructured text and detect supersession markers.
    Returns a list of Fact ORM objects ready for database insertion.
    
    Args:
        notice_text: Raw notice text to extract from
        source_id: Unique identifier for this source message
        source_type: Type of source (determines authority rank)
        timestamp: When the notice was sent
        drive_id: Placement drive identifier
        llm_client: Optional LLM client (creates new if not provided)
    
    Returns:
        List of Fact ORM objects with extracted criteria
        
    Raises:
        ValueError: If extraction fails or LLM returns invalid data
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Get authority rank for this source type
    authority_rank = SOURCE_AUTHORITY_RANK[source_type]
    
    # Build extraction prompt
    user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(
        notice_text=notice_text.strip(),
        source_type=source_type.value,
        message_id=source_id,
        timestamp=timestamp.isoformat(),
    )
    
    # Define expected output schema
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["criterion_type", "operator", "value"],
            "properties": {
                "criterion_type": {"type": "string"},
                "operator": {"type": "string"},
                "value": {"type": ["string", "number"]},
                "scope": {"type": "string"},
                "confidence": {"type": "string"},
                "is_correction": {"type": "boolean"},
                "supersedes_ref": {"type": ["string", "null"]},
                "notes": {"type": "string"},
            },
        },
    }
    
    # Call LLM with system + user prompts
    try:
        # Combine system and user prompts
        full_prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # Get structured output
        extracted_data = llm_client.generate_structured(
            prompt=full_prompt,
            schema=schema,
            temperature=0.1,  # Low temperature for deterministic extraction
        )
        
        # Handle case where LLM returns dict instead of list
        if isinstance(extracted_data, dict):
            if "criteria" in extracted_data:
                extracted_data = extracted_data["criteria"]
            elif "items" in extracted_data:
                extracted_data = extracted_data["items"]
            else:
                # Single criterion returned as dict
                extracted_data = [extracted_data]
        
        # Validate it's a list
        if not isinstance(extracted_data, list):
            raise ValueError(f"Expected list, got {type(extracted_data)}")
        
    except Exception as e:
        raise ValueError(
            f"Failed to extract criteria from notice. Error: {e}"
        ) from e
    
    # Convert extracted data to Fact ORM objects
    facts = []
    
    for item in extracted_data:
        # Validate required fields
        if not all(k in item for k in ["criterion_type", "operator", "value"]):
            continue  # Skip invalid items
        
        # Normalize criterion_type to handle common variations
        criterion_type = item["criterion_type"]
        if criterion_type in CRITERION_TYPE_ALIASES:
            criterion_type = CRITERION_TYPE_ALIASES[criterion_type]
            # Log the normalization for debugging
            print(f"INFO: Normalized {item['criterion_type']} -> {criterion_type}")
        
        # Normalize and serialize value to JSON string
        value = item["value"]
        
        # If value is already a JSON string, parse it first to avoid double-encoding
        if isinstance(value, str):
            try:
                # Try to parse - if it's already JSON, this will succeed
                parsed = json.loads(value)
                value = parsed
            except (json.JSONDecodeError, ValueError):
                # Not JSON, keep as-is (it's a plain string like "CSE")
                pass
        
        # Apply criterion-specific normalization
        if criterion_type == "allowed_branches":
            original_value = value
            value = normalize_branch_value(value)
            if value != original_value:
                print(f"INFO: Normalized branches {original_value} -> {value}")
        elif criterion_type == "deadline":
            original_value = value
            value = normalize_deadline_value(value)
            if value != original_value:
                print(f"INFO: Normalized deadline {original_value} -> {value}")
        
        # Now encode to JSON string (single encoding)
        value_str = json.dumps(value)
        
        # Create Fact ORM object
        fact = FactModel(
            source_id=source_id,
            source_type=source_type.value,
            authority_rank=authority_rank,
            timestamp=timestamp,
            effective_timestamp=timestamp,  # Default: effective immediately
            drive_id=drive_id,
            criterion_type=criterion_type,  # Use normalized type
            scope=item.get("scope", "ALL"),
            operator=item["operator"],
            value=value_str,
            is_correction=item.get("is_correction", False),
            supersedes_ref=item.get("supersedes_ref"),
            extracted_at=utcnow(),
            raw_notice_text=notice_text,
        )
        # Preserve LLM-derived metadata as transient (non-persisted) attributes so
        # downstream consumers (e.g. extract_with_confidence) can use them without
        # requiring a schema change to the immutable facts table.
        fact.extraction_confidence = item.get("confidence", "high")
        fact.extraction_notes = item.get("notes", "")
        if criterion_type == "allowed_branches":
            fact.branch_list_operation = item.get("list_operation", "replace")

        facts.append(fact)
    
    return facts


def extract_with_confidence(
    notice_text: str,
    source_id: str,
    source_type: SourceType,
    timestamp: datetime,
    drive_id: str,
    min_confidence: str = "medium",
    llm_client: LLMClient | None = None,
) -> tuple[list[FactModel], list[dict[str, Any]]]:
    """Extract criteria and split them by LLM confidence.

    Returns accepted facts (meeting ``min_confidence``, ready for DB) and
    low-confidence items (below threshold, for manual review). The LLM returns a
    per-criterion ``confidence`` field ("high" | "medium" | "low"); facts whose
    confidence ranks at or above ``min_confidence`` are accepted, the rest are
    returned as descriptive review dicts so an operator can decide whether to keep
    them.

    The confidence value is attached to each Fact as a transient
    ``extraction_confidence`` attribute by :func:`extract_criteria_from_notice`
    (it is not persisted to the immutable facts table). Items that omit a
    confidence value default to "high".

    Args:
        notice_text: Raw notice text
        source_id: Message identifier
        source_type: Source type
        timestamp: Message timestamp
        drive_id: Drive identifier
        min_confidence: Minimum confidence to accept ("high", "medium", "low")
        llm_client: Optional LLM client

    Returns:
        Tuple of (accepted_facts, low_confidence_items) where each low-confidence
        item is a dict with keys: criterion_type, operator, value, scope,
        confidence, notes, reason.
    """
    # Extract all criteria (confidence/notes attached as transient attrs)
    facts = extract_criteria_from_notice(
        notice_text=notice_text,
        source_id=source_id,
        source_type=source_type,
        timestamp=timestamp,
        drive_id=drive_id,
        llm_client=llm_client,
    )

    threshold = CONFIDENCE_RANK.get(min_confidence, CONFIDENCE_RANK["medium"])

    accepted: list[FactModel] = []
    low_confidence_items: list[dict[str, Any]] = []

    for fact in facts:
        confidence = getattr(fact, "extraction_confidence", "high")
        confidence_rank = CONFIDENCE_RANK.get(confidence, CONFIDENCE_RANK["medium"])

        if confidence_rank >= threshold:
            accepted.append(fact)
        else:
            low_confidence_items.append({
                "criterion_type": fact.criterion_type,
                "operator": fact.operator,
                "value": fact.value,
                "scope": fact.scope,
                "confidence": confidence,
                "notes": getattr(fact, "extraction_notes", ""),
                "reason": (
                    f"Extraction confidence '{confidence}' is below the "
                    f"minimum threshold '{min_confidence}'"
                ),
            })

    return accepted, low_confidence_items


def detect_supersession_explicit(
    notice_text: str,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Detect explicit supersession markers in notice text.
    
    Looks for phrases like "Correction:", "Update:", "Deadline extended", etc.
    Returns metadata about the supersession if detected.
    
    Args:
        notice_text: Raw notice text
        llm_client: Optional LLM client
    
    Returns:
        Dict with keys:
        - is_supersession: bool
        - supersession_type: "correction" | "update" | "extension" | None
        - confidence: "high" | "medium" | "low"
        - extracted_ref: str | None (reference to original notice if found)
    """
    # Simple keyword-based detection as fallback
    text_lower = notice_text.lower()
    
    supersession_keywords = {
        "correction": ["correction:", "corrected:", "mistake", "error in"],
        "update": ["update:", "updated:", "revised:", "change:"],
        "extension": ["extended to", "extension:", "postponed to", "new deadline"],
    }
    
    for supersession_type, keywords in supersession_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return {
                    "is_supersession": True,
                    "supersession_type": supersession_type,
                    "confidence": "high",
                    "extracted_ref": None,  # Could enhance with LLM to extract ref
                }
    
    return {
        "is_supersession": False,
        "supersession_type": None,
        "confidence": "high",
        "extracted_ref": None,
    }
