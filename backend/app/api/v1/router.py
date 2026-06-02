from fastapi import APIRouter
from app.api.v1 import jobs, leetcode, news

api_router = APIRouter()

# Mount feature sub-routers with structured URL prefixes and tagging definitions
api_router.include_router(jobs.router,
                          prefix="/jobs",
                          tags=["Jobs Platform"])
api_router.include_router(leetcode.router,
                          prefix="/leetcode",
                          tags=["LeetCode Tracker"])
api_router.include_router(news.router,
                          prefix="/news",
                          tags=["Tech News Synthesizer"])