try:
    import pytest
except ImportError:
    class _MockPytest:
        class mark:
            unit = staticmethod(lambda f: f)
    pytest = _MockPytest()

from app.scraping.parsers.github import (
    _parse_html_tables,
    _parse_markdown_tables,
    _clean_company,
    _clean_role,
    _clean_location,
    _extract_apply_url,
    _is_active_role,
    parse_relative_date,
)


@pytest.mark.unit
def test_clean_company():
    comp, last = _clean_company("**Google**", "OldComp")
    assert comp == "Google"
    assert last == "Google"

    # Inheritance
    comp_inherit, last_inherit = _clean_company("↳", "Google")
    assert comp_inherit == "Google"

    # Company with link
    comp_link, _ = _clean_company('<a href="https://apple.com">Apple Inc.</a>', "OldComp")
    assert comp_link == "Apple Inc."


@pytest.mark.unit
def test_clean_role():
    assert _clean_role("Software Engineer Intern 🆕") == "Software Engineer Intern"
    assert _clean_role("**Data Science Intern** 🔥") == "Data Science Intern"
    assert _clean_role("Research Intern 🔒") == "Research Intern"


@pytest.mark.unit
def test_clean_location():
    loc, is_remote = _clean_location("New York, NY<br>Remote")
    assert "New York, NY" in loc
    assert is_remote is True

    loc2, is_remote2 = _clean_location("San Francisco, CA")
    assert is_remote2 is False


@pytest.mark.unit
def test_extract_apply_url():
    # HTML link
    url1 = _extract_apply_url('<a href="https://jobs.lever.co/example/123">Apply</a>')
    assert url1 == "https://jobs.lever.co/example/123"

    # Markdown link
    url2 = _extract_apply_url("[Apply Directly](https://boards.greenhouse.io/mycorp/jobs/456)")
    assert url2 == "https://boards.greenhouse.io/mycorp/jobs/456"

    # Invalid / empty
    assert _extract_apply_url("Not a link") == ""


@pytest.mark.unit
def test_is_active_role():
    assert _is_active_role('<a href="https://test.com">Apply</a>', "SWE Intern") is True
    assert _is_active_role("🔒 Closed", "SWE Intern") is False
    assert _is_active_role('<a href="https://test.com">Apply</a>', "SWE Intern 🔒") is False


@pytest.mark.unit
def test_parse_html_tables_simplify_format():
    html = """
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>Role</th>
          <th>Location</th>
          <th>Application</th>
          <th>Age</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><a href="https://simplify.jobs/c/NextEra">NextEra Energy</a></td>
          <td>Software Engineering Intern</td>
          <td>St Paul, MN</td>
          <td><a href="https://jobs.nexteraenergy.com/job/123">Apply</a></td>
          <td>0d</td>
        </tr>
        <tr>
          <td>↳</td>
          <td>Data Analyst Intern</td>
          <td>Remote</td>
          <td><a href="https://jobs.nexteraenergy.com/job/456">Apply</a></td>
          <td>1d</td>
        </tr>
        <tr>
          <td>ClosedCorp</td>
          <td>Security Intern</td>
          <td>Austin, TX</td>
          <td>🔒 Closed</td>
          <td>2d</td>
        </tr>
      </tbody>
    </table>
    """
    jobs, skipped = _parse_html_tables(html, "https://github.com/test", include_inactive=False)
    assert len(jobs) == 2
    assert skipped == 1

    assert jobs[0].company == "NextEra Energy"
    assert jobs[0].title == "Software Engineering Intern"
    assert jobs[0].apply_url == "https://jobs.nexteraenergy.com/job/123"
    assert jobs[0].is_remote is False

    # Inherited company
    assert jobs[1].company == "NextEra Energy"
    assert jobs[1].title == "Data Analyst Intern"
    assert jobs[1].is_remote is True


@pytest.mark.unit
def test_parse_markdown_tables_speedyapply_format():
    # 6 columns: Company | Position | Location | Salary | Posting | Age
    md = """
    | Company | Position | Location | Salary | Posting | Age |
    |---|---|---|---|---|---|
    | <a href="https://meta.com"><strong>Meta</strong></a> | SWE Intern | Menlo Park, CA | $65/hr | [Apply](https://metacareers.com/jobs/1) | 0d |
    | Stripe | Backend Intern | Remote | $70/hr | [Apply](https://stripe.com/jobs/2) | 1d |
    | InactiveCo | ML Intern | Boston, MA | $50/hr | 🔒 Closed | 2d |
    """
    jobs, skipped = _parse_markdown_tables(md, "https://github.com/speedyapply", include_inactive=False)
    assert len(jobs) == 2
    assert skipped == 1
    assert jobs[0].company == "Meta"
    assert jobs[0].title == "SWE Intern"
    assert jobs[0].apply_url == "https://metacareers.com/jobs/1"
    assert jobs[1].company == "Stripe"
    assert jobs[1].is_remote is True


@pytest.mark.unit
def test_parse_markdown_tables_zshah_format():
    # 6 columns: Company | Role | Apply | Location | Skills | Posted
    md = """
    | Company | Role | Apply | Location | Skills | Posted |
    |---|---|---|---|---|---|
    | Reliable Robotics | Flight SW Intern 🆕 | [Apply](https://jobs.ashbyhq.com/rr/1) | Mountain View, CA | Python | Sep 10 |
    | Aurora Innovation | Vehicle Platform Intern | [Apply](https://jobs.ashbyhq.com/aurora/2) | Remote | C++ | Sep 12 |
    """
    jobs, skipped = _parse_markdown_tables(md, "https://github.com/zshah", include_inactive=False)
    assert len(jobs) == 2
    assert skipped == 0
    assert jobs[0].company == "Reliable Robotics"
    assert jobs[0].title == "Flight SW Intern"
    assert jobs[0].location == "Mountain View, CA"
    assert jobs[0].apply_url == "https://jobs.ashbyhq.com/rr/1"
    assert jobs[1].is_remote is True
