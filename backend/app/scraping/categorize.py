"""
Ingest-time job classification: category and company domain.

Category used to be computed per request with substring ILIKEs
(`company ILIKE '%meta%'`, `'%sig%'`, ...), which matched Metabase,
"Design", "Signify" and friends, and forced 30+ OR'd unindexable scans on
every filtered page. It is now computed once, by whole-word match on the
normalized company name, and stored in an indexed column.

The SQL backfill in alembic revision 7c1d9e3f4a20 snapshots these lists;
update both together.
"""
import re
from typing import Optional
from urllib.parse import urlparse

CATEGORY_FAANG = "FAANG+"
CATEGORY_QUANT = "Quant"
CATEGORY_OTHERS = "Others"

FAANG_COMPANIES = (
    "meta", "apple", "amazon", "netflix", "google", "microsoft", "nvidia",
    "tesla", "tiktok", "bytedance",
)
QUANT_COMPANIES = (
    "jane street", "citadel", "two sigma", "hrt", "hudson river trading",
    "optiver", "jump trading", "akuna", "drw", "imc", "tower research",
    "point72", "de shaw", "d e shaw", "deshaw", "renaissance technologies",
    "susquehanna", "sig",
)
QUANT_TITLE_TERMS = ("quant", "quantitative", "algorithmic", "algo", "trading", "hft")


def _words(text: str) -> str:
    """Lowercase, punctuation -> spaces, padded so ' x ' is a whole-word test."""
    return " " + re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip() + " "


def _has_any(haystack: str, needles) -> bool:
    return any(f" {n} " in haystack for n in needles)


def categorize(company: str, title: str) -> str:
    company_w = _words(company)
    if _has_any(company_w, FAANG_COMPANIES):
        return CATEGORY_FAANG
    if _has_any(company_w, QUANT_COMPANIES) or _has_any(_words(title), QUANT_TITLE_TERMS):
        return CATEGORY_QUANT
    return CATEGORY_OTHERS


# Hosts that belong to an ATS or aggregator, not to the hiring company.
_NON_COMPANY_HOSTS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com",
    "smartrecruiters.com", "workable.com", "icims.com", "jobvite.com",
    "bamboohr.com", "recruitee.com", "breezy.hr", "rippling.com",
    "linkedin.com", "github.com", "simplify.jobs", "indeed.com",
    "wellfound.com", "oraclecloud.com", "taleo.net", "successfactors.com",
    "eightfold.ai", "dayforcehcm.com", "paylocity.com", "adp.com",
    "workatastartup.com", "ycombinator.com",  # YC's board, not the employer
)
_TWO_LABEL_SUFFIXES = ("co.uk", "com.au", "co.jp", "co.in", "com.br", "com.sg", "co.kr")


def company_domain(apply_url: Optional[str]) -> Optional[str]:
    """
    The hiring company's registrable domain, when the apply link is on the
    company's own site (careers.stripe.com -> stripe.com). None for ATS-
    hosted links, where the host says nothing about the company.
    """
    host = (urlparse(apply_url or "").hostname or "").lower()
    if not host or any(host == h or host.endswith("." + h) for h in _NON_COMPANY_HOSTS):
        return None
    labels = host.split(".")
    if len(labels) < 2:
        return None
    keep = 3 if ".".join(labels[-2:]) in _TWO_LABEL_SUFFIXES else 2
    return ".".join(labels[-keep:])
