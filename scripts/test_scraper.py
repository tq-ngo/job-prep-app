# import asyncio
# import os
# import sys

# # Load environment variables manually from .env
# def load_env():
#     env_path = os.path.join(os.path.dirname(__file__), ".env")
#     if os.path.exists(env_path):
#         with open(env_path, "r") as f:
#             for line in f:
#                 line = line.strip()
#                 if not line or line.startswith("#"):
#                     continue
#                 if "=" in line:
#                     key, val = line.split("=", 1)
#                     # Strip quotes if present
#                     val = val.strip().strip('"').strip("'")
#                     os.environ[key.strip()] = val
#         print("Loaded environment variables from .env")
#     else:
#         print("Warning: .env file not found. Using current system environment.")

# # Add parent directory to sys.path so we can import 'app'
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# from app.services.scrapers.linkedin import LinkedInScraper

# async def test_scraper():
#     load_env()
    
#     # Verify cookie presence
#     cookie = os.getenv("LINKEDIN_LI_AT", "")
#     if not cookie:
#         print("Error: LINKEDIN_LI_AT session cookie is missing. Please set it in backend/.env")
#         return
        
#     print(f"Detected LI_AT cookie (length: {len(cookie)} chars)")

#     # Sample search URL - Software Engineer jobs in San Francisco
#     search_url = "https://www.linkedin.com/jobs/search/?keywords=software%20engineer&location=San%20Francisco%20Bay%20Area"
    
#     print(f"Initializing LinkedInScraper...")
#     scraper = LinkedInScraper()
    
#     # Temporarily override circuit breaker check for testing
#     scraper.cb.is_open = lambda: False
    
#     print(f"Fetching and parsing jobs from: {search_url}")
#     print("This will spin up a headless Playwright instance and scroll through pages. Please wait...")
    
#     try:
#         jobs = await scraper.fetch_and_parse(search_url)
#         print("\n--- Scraping Results Summary ---")
#         print(f"Total jobs extracted: {len(jobs)}")
        
#         # Display the first 5 jobs
#         for idx, job in enumerate(jobs[:5]):
#             print(f"\n[{idx + 1}] {job['job_title']}")
#             print(f"    Company:  {job['company_name']}")
#             print(f"    Location: {job['location']}")
#             print(f"    URL:      {job['job_url']}")
            
#         if len(jobs) > 5:
#             print(f"\n... and {len(jobs) - 5} more jobs.")
            
#     except Exception as e:
#         print(f"\nAn error occurred during execution: {e}")

# if __name__ == "__main__":
#     asyncio.run(test_scraper())
