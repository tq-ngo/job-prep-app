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
        
        # Regex to isolate the table rows and individual cell contents
        tr_pattern = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
        td_pattern = re.compile(r"<td>(.*?)</td>", re.DOTALL)
        
        # Regex for specific data points within the HTML
        company_name_pattern = re.compile(r"<strong>.*?<a[^>]*>(.*?)</a>.*?</strong>", re.DOTALL)
        apply_url_pattern = re.compile(r'<a href="([^"]+)"[^>]*><img[^>]*alt="Apply"', re.DOTALL)
        
        last_company = ""
        
        for tr_match in tr_pattern.finditer(markdown_text):
            td_content = td_pattern.findall(tr_match.group(1))
            
            # The target table structure has 5 columns: Company, Role, Location, Application, Age
            if len(td_content) < 4:
                continue
                
            company_raw = td_content[0].strip()
            role_raw = td_content[1].strip()
            location_raw = td_content[2].replace("<br>", ", ").replace("<br/>", ", ").strip()
            application_raw = td_content[3].strip()
            
            # Handle nested roles (↳ symbol)
            if "↳" in company_raw:
                company_name = last_company
            else:
                # Extract clean company name from the link inside strong tags
                name_match = company_name_pattern.search(company_raw)
                if name_match:
                    company_name = name_match.group(1).strip()
                else:
                    # Fallback: strip all tags if the structure is different
                    company_name = re.sub(r'<[^>]+>', '', company_raw).strip()
                
                # Filter out emoji markers like 🔥
                company_name = company_name.split(" ")[-1] if " " in company_name else company_name
                last_company = company_name
            
            # Extract the direct application URL from the "Apply" image link
            url_match = apply_url_pattern.search(application_raw)
            if not url_match:
                continue
                
            url = url_match.group(1)
            
            # Clean role and location of any remaining HTML tags
            role = re.sub(r'<[^>]+>', '', role_raw).strip()
            location = re.sub(r'<[^>]+>', '', location_raw).strip()
            
            extracted_jobs.append({
                "company_name": company_name,
                "job_title": role,
                "location": location,
                "job_url": url,
                "source": "Simplify GitHub"
            })

        return extracted_jobs