import pytest

from app.scraping.categorize import (
    categorize,
    company_domain,
    CATEGORY_FAANG,
    CATEGORY_QUANT,
    CATEGORY_OTHERS,
)


@pytest.mark.unit
def test_categorize_faang():
    assert categorize("Google", "Software Engineer") == CATEGORY_FAANG
    assert categorize("Apple, Inc.", "iOS Intern") == CATEGORY_FAANG
    assert categorize("Meta Platforms", "Production Engineer") == CATEGORY_FAANG
    assert categorize("Tesla Motors", "Firmware Engineer") == CATEGORY_FAANG
    assert categorize("Netflix", "Backend Intern") == CATEGORY_FAANG


@pytest.mark.unit
def test_categorize_quant():
    # By company name
    assert categorize("Citadel", "Software Developer") == CATEGORY_QUANT
    assert categorize("Jane Street", "Software Engineer") == CATEGORY_QUANT
    assert categorize("Two Sigma", "Data Scientist") == CATEGORY_QUANT
    assert categorize("Hudson River Trading", "C++ Developer") == CATEGORY_QUANT
    assert categorize("Optiver", "Execution Trader") == CATEGORY_QUANT

    # By title terms
    assert categorize("Unknown Boutique", "Quantitative Researcher") == CATEGORY_QUANT
    assert categorize("Alpha Group", "Algorithmic Trading Intern") == CATEGORY_QUANT
    assert categorize("Fintech Corp", "HFT C++ Engineer") == CATEGORY_QUANT


@pytest.mark.unit
def test_categorize_whole_word_matching_prevents_false_positives():
    # Substring matches that previously triggered false positives
    assert categorize("Metabase", "SWE") == CATEGORY_OTHERS
    assert categorize("Design Studio", "Frontend Intern") == CATEGORY_OTHERS
    assert categorize("Signify Health", "Full Stack Developer") == CATEGORY_OTHERS
    assert categorize("SigFig", "Software Engineer") == CATEGORY_OTHERS
    assert categorize("Quantcast", "Software Engineer") == CATEGORY_OTHERS


@pytest.mark.unit
def test_company_domain_extraction():
    # Direct company careers pages
    assert company_domain("https://careers.stripe.com/jobs/123") == "stripe.com"
    assert company_domain("https://jobs.netflix.com/jobs/456") == "netflix.com"
    assert company_domain("https://engineering.co.uk/apply") == "engineering.co.uk"

    # ATS-hosted boards should return None (not hiring company's domain)
    assert company_domain("https://boards.greenhouse.io/stripe/jobs/123") is None
    assert company_domain("https://jobs.lever.co/databricks/456") is None
    assert company_domain("https://stripe.myworkdayjobs.com/en-US/careers") is None
    assert company_domain("https://jobs.ashbyhq.com/scale/789") is None
    assert company_domain("https://www.linkedin.com/jobs/view/123") is None
    assert company_domain(None) is None

