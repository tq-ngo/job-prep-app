import httpx
import re
from typing import List, Dict

class SimplifyScraper:
    TARGET_URL = "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/refs/heads/dev/README.md"

    async def fetch_and_parse(self) -> List[Dict[str, str]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.TARGET_URL)
            if response.status_code != 200:
                raise Exception("Unable to pull markdown repository stream.")
            
        return self._extract_table_data(response.text)

    def _extract_table_data(self, markdown_text: str) -> List[Dict[str, str]]:
        extracted_jobs = []
        last_company = ""
        
        # Regex to extract href values from application link cell
        link_pattern = re.compile(r'href="([^"]+)"')
        
        # Regex to extract text inside HTML anchors if present
        anchor_text_pattern = re.compile(r'<a[^>]*>(.*?)</a>')
        
        # Split markdown text by lines
        lines = markdown_text.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line.startswith("|"):
                continue
            
            # Split line by markdown pipes
            parts = [p.strip() for p in line.split("|")]
            
            # Valid row starts and ends with |, split yields: ["", Company, Role, Location, Application, Date, ""]
            if len(parts) < 6:
                continue
                
            # Filter out headers and dividers
            if "company" in parts[1].lower() or "---" in parts[1]:
                continue
                
            company_raw = parts[1]
            role_raw = parts[2]
            location_raw = parts[3]
            application_raw = parts[4]
            
            if not role_raw or not application_raw:
                continue
                
            # 1. Extract Company Name
            if "↳" in company_raw or company_raw == "":
                company_name = last_company
            else:
                # If there's an HTML link in the company column, extract text
                anchor_match = anchor_text_pattern.search(company_raw)
                if anchor_match:
                    company_name = anchor_match.group(1).strip()
                else:
                    # Strip any HTML tags or markdown links
                    company_name = re.sub(r'<[^>]+>', '', company_raw).strip()
                    company_name = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', company_name).strip()
                
                # Strip hot markers / icons
                company_name = company_name.replace("🔥", "").strip()
                last_company = company_name
            
            # 2. Extract Application URL
            url_match = link_pattern.search(application_raw)
            if not url_match:
                continue
            url = url_match.group(1)
            
            # 3. Clean Role and Location metadata
            role = re.sub(r'<[^>]+>', '', role_raw).strip()
            role = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', role).strip()
            
            location = re.sub(r'<[^>]+>', '', location_raw).replace("<br>", ", ").replace("<br/>", ", ").strip()
            location = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', location).strip()
            
            # Filter out closed roles (legend 🔒)
            if "🔒" in role or "🔒" in application_raw:
                continue
                
            extracted_jobs.append({
                "company_name": company_name,
                "job_title": role,
                "location": location,
                "job_url": url,
                "source": "Simplify GitHub"
            })
            
        return extracted_jobs