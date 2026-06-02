from typing import List, Dict
from playwright.async_api import async_playwright, Page


class PlaywrightScraper:
    """
    Handles scraping of JS-rendered job boards that httpx cannot reach.
    Isolated from persistence logic — returns raw data only.
    """

    async def scrape_job_board(
        self,
        target_url: str,
        card_selector: str = ".job-card",
        title_selector: str = ".title",
        company_selector: str = ".company",
        location_selector: str = ".location",
        link_selector: str = "a.job-link",
    ) -> List[Dict[str, str]]:
        """
        Generic JS job board scraper. Selectors are configurable per board.
        Returns a list of raw job dicts with whatever fields are extractable.
        """
        results: List[Dict[str, str]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(target_url, wait_until="networkidle", timeout=30_000)
                results = await self._extract_cards(
                    page, card_selector, title_selector, company_selector, location_selector
                )
            finally:
                # Always close browser even if extraction raises
                await browser.close()

        return results

    async def _extract_cards(
        self,
        page: Page,
        card_selector: str,
        title_selector: str,
        company_selector: str,
        location_selector: str,
        link_selector: str,
    ) -> List[Dict[str, str]]:
        """Extract text fields from each job card found on the page."""
        cards = await page.query_selector_all(card_selector)
        results = []

        for card in cards:
            job: Dict[str, str] = {"source": page.url}

            title_el = await card.query_selector(title_selector)
            if title_el:
                job["title"] = (await title_el.inner_text()).strip()

            company_el = await card.query_selector(company_selector)
            if company_el:
                job["company"] = (await company_el.inner_text()).strip()

            location_el = await card.query_selector(location_selector)
            if location_el:
                job["location"] = (await location_el.inner_text()).strip()

            link_el = await card.query_selector(link_selector)
            if link_el:
                raw_url = await link_el.get_attribute("href")
                if raw_url:
                    # Resolve relative URLs if necessary
                    job["url"] = raw_url.strip() if raw_url.startswith("http") else f"{page.url.rstrip('/')}/{raw_url.lstrip('/')}"

            # Only append if we got at least a title
            if job.get("title") and job.get("url"):
                results.append(job)

        return results