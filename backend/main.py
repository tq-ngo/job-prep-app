from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import init_db
from contextlib import asynccontextmanager

async def init_elasticsearch_index():
    import asyncio
    try:
        from app.services.search_service import SearchService
        search_svc = SearchService()
        for i in range(20):
            if search_svc.is_healthy():
                search_svc.create_job_index()
                print("Elasticsearch job index initialized successfully.")
                return
            print(f"Waiting for Elasticsearch to become healthy (attempt {i+1}/20)...")
            await asyncio.sleep(3)
        print("Warning: Failed to initialize Elasticsearch index (service offline).")
    except Exception as e:
        print(f"Failed to initialize Elasticsearch index in background: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Triggers table creation asynchronously on system startup
    await init_db()
    
    # Start Elasticsearch index creation in the background
    import asyncio
    asyncio.create_task(init_elasticsearch_index())
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Configure cross-origin sharing patterns for Next.js communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten down to domain definitions during live deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}