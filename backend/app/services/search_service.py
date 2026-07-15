# import logging
# from typing import List, Dict, Any, Optional
# from elasticsearch import Elasticsearch
# from app.config import settings

# logger = logging.getLogger(__name__)

# class SearchService:
#     def __init__(self):
#         self.es_url = settings.ELASTICSEARCH_URL
#         self.client: Optional[Elasticsearch] = None
#         self._connect()

#     def _connect(self):
#         try:
#             # Initialize Elasticsearch client with reasonable timeouts
#             self.client = Elasticsearch(
#                 self.es_url,
#                 request_timeout=5,
#                 max_retries=3,
#                 retry_on_timeout=True
#             )
#             # Ping to verify connectivity
#             if not self.client.ping():
#                 logger.warning("Elasticsearch ping failed. Search service will run in fallback mode.")
#                 self.client = None
#         except Exception as e:
#             logger.error(f"Failed to initialize Elasticsearch client: {e}. Running in fallback mode.")
#             self.client = None

#     def is_healthy(self) -> bool:
#         if not self.client:
#             self._connect()
#         return self.client is not None

#     def create_job_index(self):
#         """Creates the jobs index with appropriate mapping configurations."""
#         if not self.is_healthy():
#             return

#         index_name = "jobs"
#         mappings = {
#             "mappings": {
#                 "properties": {
#                     "title": { "type": "text", "analyzer": "english" },
#                     "title_normalized": { "type": "keyword" },
#                     "company": { "type": "keyword" },
#                     "description": { "type": "text", "analyzer": "english" },
#                     "skills": { "type": "keyword" },
#                     "seniority": { "type": "keyword" },
#                     "remote_policy": { "type": "keyword" },
#                     "location": { "type": "keyword" },
#                     "salary_min_usd": { "type": "integer" },
#                     "salary_max_usd": { "type": "integer" },
#                     "quality_score": { "type": "short" },
#                     "is_active": { "type": "boolean" },
#                     "posted_at": { "type": "date" }
#                 }
#             }
#         }

#         try:
#             if not self.client.indices.exists(index=index_name):
#                 self.client.indices.create(index=index_name, body=mappings)
#                 logger.info(f"Successfully created Elasticsearch index: {index_name}")
#         except Exception as e:
#             logger.error(f"Error creating Elasticsearch index: {e}")

#     def index_job(self, job_id: str, job_data: Dict[str, Any]):
#         """Indexes or updates a job in Elasticsearch."""
#         if not self.is_healthy():
#             logger.debug("ES not healthy, skipping index_job.")
#             return

#         try:
#             doc = {
#                 "title": job_data.get("title_raw", ""),
#                 "title_normalized": job_data.get("title_normalized", ""),
#                 "company": job_data.get("company_name", ""),
#                 "description": job_data.get("description_text", ""),
#                 "skills": job_data.get("skills_required", []),
#                 "seniority": job_data.get("seniority", "mid"),
#                 "remote_policy": job_data.get("remote_policy", "onsite"),
#                 "location": f"{job_data.get('location_city', '')}, {job_data.get('location_country', '')}".strip(", "),
#                 "salary_min_usd": job_data.get("salary_min_usd"),
#                 "salary_max_usd": job_data.get("salary_max_usd"),
#                 "quality_score": job_data.get("quality_score", 0),
#                 "is_active": job_data.get("is_active", True),
#                 "posted_at": job_data.get("first_seen_at", "")
#             }
#             self.client.index(index="jobs", id=str(job_id), document=doc, refresh=True)
#             logger.debug(f"Indexed job {job_id} successfully in Elasticsearch.")
#         except Exception as e:
#             logger.error(f"Error indexing job {job_id} in Elasticsearch: {e}")

#     def search_jobs(
#         self,
#         query: Optional[str] = None,
#         skills: Optional[List[str]] = None,
#         remote_only: bool = False,
#         min_salary: Optional[int] = None,
#         skip: int = 0,
#         limit: int = 20
#     ) -> Optional[Dict[str, Any]]:
#         """
#         Executes job search on Elasticsearch.
#         Returns the raw ES response if successful, otherwise None (indicating fallback needed).
#         """
#         if not self.is_healthy():
#             return None

#         must = []
#         filter_clauses = [{"term": {"is_active": True}}]

#         if query:
#             must.append({
#                 "multi_match": {
#                     "query": query,
#                     "fields": ["title^3", "skills^2", "description"],
#                     "fuzziness": "AUTO",
#                     "type": "best_fields"
#                 }
#             })
        
#         if skills:
#             filter_clauses.append({"terms": {"skills": skills}})
        
#         if remote_only:
#             filter_clauses.append({"term": {"remote_policy": "remote"}})
            
#         if min_salary:
#             filter_clauses.append({"range": {"salary_min_usd": {"gte": min_salary}}})

#         body = {
#             "from": skip,
#             "size": limit,
#             "query": {
#                 "bool": {
#                     "must": must or [{"match_all": {}}],
#                     "filter": filter_clauses
#                 }
#             },
#             "sort": [
#                 {"_score": "desc"},
#                 {"quality_score": "desc"},
#                 {"posted_at": "desc"}
#             ],
#             "aggs": {
#                 "seniority": {"terms": {"field": "seniority"}},
#                 "remote_policy": {"terms": {"field": "remote_policy"}},
#                 "top_skills": {"terms": {"field": "skills", "size": 20}}
#             }
#         }

#         try:
#             res = self.client.search(index="jobs", body=body)
#             return res.body
#         except Exception as e:
#             logger.error(f"Elasticsearch search failed: {e}. Forcing DB fallback.")
#             return None
