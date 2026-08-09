from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery app
# The first argument is the name of the current module (for task naming)
celery_app = Celery(
    "job-prep-app",
    broker=settings.CELERY_BROKER_URL,      # Where tasks are sent
    backend=settings.CELERY_RESULT_BACKEND,  # Where results are stored
    include=[
        "app.tasks.job_tasks",
        "app.tasks.news_tasks",
    ],
)

# Configuration
celery_app.conf.update(
    # Task routing: different task types go to different queues
    # This lets you scale scraping workers independently from AI workers
    task_routes={
        "app.tasks.job_tasks.scrape_github": {"queue": "scraping"},
        "app.tasks.job_tasks.scrape_linkedin": {"queue": "scraping"},
        "app.tasks.job_tasks.enrich_job_with_ai": {"queue": "ai"},
        "app.tasks.job_tasks.process_raw_jobs_batch": {"queue": "ai"},
        "app.tasks.news_tasks.crawl_news_site": {"queue": "scraping"},
        "app.tasks.news_tasks.scrape_linkedin_news": {"queue": "scraping"},
        "app.tasks.news_tasks.summarize_article": {"queue": "ai"},
    },
    
    # Serialization: JSON is readable and cross-language compatible
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task acknowledgment: 'late_ack' means the task is acknowledged
    # AFTER completion, not before. This prevents task loss if the worker
    # crashes mid-execution — the task goes back to the queue.
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Only take one task at a time
    
    # Keep results in Redis for 1 hour
    result_expires=3600,

    beat_schedule={
        "scrape-github-every-6h": {
            "task": "app.tasks.job_tasks.scrape_github",
            "schedule": 6 * 60 * 60,
        },
        # LinkedIn runs at 06:00 UTC daily
        "scrape-linkedin-daily": {
            "task": "app.tasks.job_tasks.scrape_linkedin",
            "schedule": crontab(hour=6, minute=0),
            "args": ("https://www.linkedin.com/jobs/search/?keywords=software+engineer+intern",),
        },
        "enrich-raw-jobs-every-minute": {
            "task": "app.tasks.job_tasks.process_raw_jobs_batch",
            "schedule": 60,
            "kwargs": {"batch_size": 10},
        },
    },
)