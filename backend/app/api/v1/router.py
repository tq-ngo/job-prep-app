from fastapi import APIRouter
from app.api.v1 import jobs, leetcode, news, auth

api_router = APIRouter()

api_router.include_router(auth.router,
                          prefix="/auth",
                          tags=["Authentication"])
api_router.include_router(jobs.router,
                          prefix="/jobs",
                          tags=["Jobs Platform"])
api_router.include_router(leetcode.router,
                          prefix="/leetcode",
                          tags=["LeetCode Tracker"])
api_router.include_router(news.router,
                          prefix="/news",
                          tags=["Tech News Synthesizer"])