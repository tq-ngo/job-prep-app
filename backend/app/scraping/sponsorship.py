"""
Visa sponsorship analysis and classification for job listings.

Analyzes job descriptions and titles to determine eligibility for:
- CPT/OPT (F-1 visa students)
- H-1B visa sponsorship
- US citizenship / security clearance / ITAR constraints
"""
import re
from typing import Dict, Any, Optional

CITIZENSHIP_PATTERNS = (
    r"\b(?:u\.?s\.?\s+citizen(?:ship)?\s+(?:required|only|status)|must be a u\.?s\.?\s+citizen)\b",
    r"\bu\.?s\.?\s+person\s+(?:required|only|status)\b",
    r"\b(?:security clearance\b|active secret clearance\b|top secret\b|dod clearance\b)",
    r"\b(?:itar\b|export control laws?\b|export administration regulations?\b)",
)

NO_SPONSORSHIP_PATTERNS = (
    r"\b(?:will not sponsor|does not sponsor|no visa sponsorship|not eligible for (?:visa\s+)?sponsorship)\b",
    r"\bwithout (?:the\s+)?need for (?:visa\s+)?sponsorship\b",
    r"\bsponsorship (?:is\s+)?not available\b",
    r"\bunable to (?:provide\s+)?sponsor(?:ship)?\b",
)

H1B_SPONSOR_PATTERNS = (
    r"\b(?:visa sponsorship (?:is\s+)?available|h-?1b sponsorship|offers? (?:visa\s+)?sponsorship)\b",
    r"\b(?:will sponsor (?:work\s+)?visas?|provides? (?:visa\s+)?sponsorship)\b",
    r"\bsponsorship available for eligible candidates\b",
)

CPT_OPT_PATTERNS = (
    r"\b(?:cpt|opt|f-?1\s+visa|f-?1\s+students?|stem\s+opt)\b",
    r"\baccepts? cpt\b",
    r"\bopt eligible\b",
)


def _matches_any(text: str, patterns) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def classify_sponsorship(title: Optional[str] = "", description: Optional[str] = "") -> Dict[str, Any]:
    """
    Classifies visa sponsorship for a job posting from its title and description.
    """
    text = f"{title or ''} {description or ''}"
    
    requires_citizenship = _matches_any(text, CITIZENSHIP_PATTERNS)
    no_sponsorship = _matches_any(text, NO_SPONSORSHIP_PATTERNS)
    offers_h1b = _matches_any(text, H1B_SPONSOR_PATTERNS)
    explicit_cpt_opt = _matches_any(text, CPT_OPT_PATTERNS)
    
    if requires_citizenship:
        status = "citizenship"
        label = "US Citizen Required"
        is_f1_eligible = False
    elif offers_h1b:
        status = "h1b"
        label = "H-1B Sponsor"
        is_f1_eligible = True
    elif no_sponsorship:
        status = "no_sponsorship"
        label = "No Sponsorship"
        is_f1_eligible = False
    elif explicit_cpt_opt or (not requires_citizenship and not no_sponsorship):
        status = "cpt_opt"
        label = "CPT/OPT Sponsor"
        is_f1_eligible = True
    else:
        status = "cpt_opt"
        label = "CPT/OPT Sponsor"
        is_f1_eligible = True

    return {
        "status": status,
        "label": label,
        "is_f1_eligible": is_f1_eligible,
        "requires_citizenship": requires_citizenship,
        "offers_h1b": offers_h1b,
    }

