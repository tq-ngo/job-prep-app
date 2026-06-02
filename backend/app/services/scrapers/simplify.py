import httpx
import re
from typing import List, Dict

class SimplifyScraper:
    TARGET_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"

    async def fetch_and_parse(self) -> List[Dict[str, str]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.TARGET_URL)
            if response.status_code != 200:
                raise Exception("Unable to pull markdown repository stream.")
            
        return self._extract_table_data(response.text)

    def _extract_table_data(self, markdown_text: str) -> List[Dict[str, str]]:
        extracted_jobs = []
        # Find lines resembling typical markdown pipeline data: | Company | Role | Location | Link |
        row_pattern = re.compile(r"\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|")
        url_pattern = re.compile(r"\((https?://[^)]+)\)")
        
        for line in markdown_text.splitlines():
            # Only process rows that have an actionable or locked status
            if "Apply" not in line and "🔒" not in line:
                continue
 
            matches = row_pattern.findall(line)
            if not matches:
                continue
 
            comp, role, loc, terms, link_col = [col.strip() for col in matches[0]]
 
            # Strip markdown bold markers from company name if present
            comp = re.sub(r"\*\*([^*]+)\*\*", r"\1", comp).strip()
 
            url_match = url_pattern.search(link_col)
            url = url_match.group(1) if url_match else ""
 
            # Skip rows with no usable URL (locked roles without a link)
            if not url:
                continue
                    
            extracted_jobs.append({
                "company_name": comp,
                "job_title": role.strip(),
                "location": loc.strip(),
                "job_url": url,
                "source": "Simplify GitHub"
            })

        return extracted_jobs