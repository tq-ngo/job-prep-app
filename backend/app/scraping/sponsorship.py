"""
Visa sponsorship analysis and classification for job listings.

Analyzes job descriptions and titles to determine eligibility for:
- Sponsorship Available (explicit CPT/OPT or H-1B visa sponsorship)
- US Citizen Required (citizenship, clearance, or ITAR constraints)
- Default: unconfirmed postings are left untagged
"""
import re
from typing import Dict, Any, Optional

CITIZENSHIP_PATTERNS = (
    r"\b(?:u\.?s\.?\s+citizen(?:ship)?\s+(?:required|only|is required|mandatory)|must be a u\.?s\.?\s+citizen)\b",
    r"\b(?:you are a|must be a|candidates? must be a|applicants? must be a)\s+u\.?s\.?\s+citizen\b",
    r"\bu\.?s\.?\s+citizen(?:ship)?\s*,\s*(?:u\.?s\.?\s+)?permanent resident\b",
    r"\bu\.?s\.?\s+citizen(?:ship)?\s+(?:or|and)\s+(?:u\.?s\.?\s+)?permanent resident\b",
    r"\b(?:requires?\s+)?u\.?s\.?\s+citizenship\s+(?:required|or\s+permanent\s+residency)\b",
    r"\bu\.?s\.?\s+person\s+(?:required|only|status)\b",
    r"\b(?:security clearance\b|active secret clearance\b|top secret\b|dod clearance\b)",
    r"\b(?:itar\b|export control laws?\b|export administration regulations?\b)",
    r"\b(?:requires? (?:u\.?s\.?\s+)?citizenship|requires? (?:security\s+)?clearance)\b",
)

NO_SPONSORSHIP_PATTERNS = (
    r"\b(?:will not sponsor|does not sponsor|no visa sponsorship|not eligible for (?:visa\s+)?sponsorship)\b",
    r"\b(?:does\s+not|will\s+not|cannot|can\s+not|not\s+able\s+to)\s+(?:offer|provide)\s+(?:work\s+)?(?:visa\s+)?sponsorship\b",
    r"\bwithout (?:the\s+)?need for (?:visa\s+)?sponsorship\b",
    r"(?<!with or )\bwithout\s+(?:[\w\s]{1,30}\s+)?sponsorship\b",
    r"\bsponsorship (?:is\s+)?not available\b",
    r"\bunable to (?:provide\s+|offer\s+)?(?:work\s+)?(?:visa\s+)?sponsor(?:ship)?\b",
    r"\bnot able to sponsor\b",
    r"\b(?:must\s+not\s+require|does\s+not\s+require|will\s+not\s+require)\s+(?:work\s+)?(?:visa\s+)?sponsorship\b",
    r"\bnot\s+provide\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:f-?1|cpt|opt|j-?1|m-?1)\s+(?:students?|visas?|candidates?)?\s+(?:are\s+)?not\s+eligible\b",
    r"\bnot\s+eligible\s+(?:to\s+apply\s+)?(?:due\s+to|for|on)\s+(?:any\s+)?(?:student|exchange|f-?1|cpt|opt|visa)\b",
)

SPONSORSHIP_AVAILABLE_PATTERNS = (
    r"\b(?:visa sponsorship (?:is\s+)?available|offers? (?:visa\s+)?sponsorship|will sponsor (?:work\s+)?visas?|provides? (?:visa\s+)?sponsorship|sponsorship (?:is\s+)?available for (?:eligible\s+)?candidates)\b",
    r"\b(?:visa sponsorship provided|company(?:-|\s+)sponsored visas?)\b",
    r"\b(?:h-?1b (?:sponsorship|sponsor|visa support|transfer))\b",
    r"\b(?:sponsors? h-?1b|will sponsor h-?1b|offers? h-?1b)\b",
    r"\b(?:accepts?\s+(?:cpt|opt)|(?:cpt|opt)\s+accepted|cpt/opt\s+eligible|eligible\s+for\s+(?:cpt|opt))\b",
    r"\b(?:welcomes?\s+cpt\b|welcomes?\s+opt\b|welcomes?\s+f-?1\s+students?|f-?1\s+visa\s+sponsorship)\b",
    r"\b(?:cpt\s+and\s+opt\s+students?\s+welcome|cpt/opt\s+sponsorship)\b",
)


def _matches_any(text: str, patterns) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def classify_sponsorship(title: Optional[str] = "", description: Optional[str] = "") -> Dict[str, Any]:
    """
    Classifies visa sponsorship for a job posting from its title and description.
    Rules:
    - Clearly states citizenship/clearance: status="citizenship", label="US Citizen Required"
    - Clearly states no sponsorship: status="no_sponsorship", label="No Sponsorship"
    - Clearly states positive sponsorship: status="sponsorship_available", label="Sponsorship Available"
    - Otherwise unconfirmed: status=None, label=None (leave untagged)
    """
    text = f"{title or ''} {description or ''}"
    
    requires_citizenship = _matches_any(text, CITIZENSHIP_PATTERNS)
    no_sponsorship = _matches_any(text, NO_SPONSORSHIP_PATTERNS)
    offers_sponsorship = _matches_any(text, SPONSORSHIP_AVAILABLE_PATTERNS)
    
    if requires_citizenship:
        status = "citizenship"
        label = "US Citizen Required"
        is_f1_eligible = False
    elif no_sponsorship:
        status = "no_sponsorship"
        label = "No Sponsorship"
        is_f1_eligible = False
    elif offers_sponsorship:
        status = "sponsorship_available"
        label = "Sponsorship Available"
        is_f1_eligible = True
    else:
        # Not completely confirmed: leave untagged
        status = None
        label = None
        is_f1_eligible = True

    return {
        "status": status,
        "label": label,
        "is_f1_eligible": is_f1_eligible,
        "requires_citizenship": requires_citizenship,
        "offers_sponsorship": offers_sponsorship,
    }
