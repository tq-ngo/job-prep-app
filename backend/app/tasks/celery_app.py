from celery import Celery
from celery.schedules import crontab
from app.config import settings
from app.tasks.runtime import DEFAULT_TASK_TIMEOUT, HARD_LIMIT_GRACE

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
        "app.tasks.job_tasks.requeue_stuck_jobs": {"queue": "ai"},
        "app.tasks.job_tasks.deactivate_stale_jobs": {"queue": "default"},
        "app.tasks.job_tasks.backfill_descriptions": {"queue": "scraping"},
        "app.tasks.news_tasks.crawl_news_site": {"queue": "scraping"},
        "app.tasks.news_tasks.summarize_article": {"queue": "ai"},
        "app.tasks.news_tasks.scrape_linkedin_news": {"queue": "scraping"},
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
    # With acks_late, Redis redelivers any message unacknowledged after the
    # visibility timeout — by default 1h, less than a long crawl plus its
    # retry countdowns, so a healthy run could be delivered a second time.
    # task_reject_on_worker_lost is deliberately NOT enabled: a task killed
    # by its hard time limit counts as "worker lost", and requeueing it
    # would loop a hung crawl forever.
    broker_transport_options={"visibility_timeout": 2 * 60 * 60},

    # Hard backstop for every task. Each body is also bounded in-loop by
    # tasks/runtime.run_async (DEFAULT_TASK_TIMEOUT unless the task sets its
    # own), which cancels cleanly so locks are released; this kills the
    # process only if that somehow didn't happen. Long tasks (scrapes,
    # backfill) set a larger time_limit on their decorators. No soft limit:
    # see runtime.py for why it can't work under async_to_sync.
    task_time_limit=DEFAULT_TASK_TIMEOUT + HARD_LIMIT_GRACE,

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
        # Counterpart to the raw->queued claim in process_raw_jobs_batch:
        # returns rows stranded by a worker that died mid-enrichment.
        # 60 min: comfortably longer than a job can legitimately wait now
        # that the batch caps the queue. At 30 min it requeued jobs that were
        # still waiting their turn, and they were enriched twice.
        "requeue-stuck-jobs": {
            "task": "app.tasks.job_tasks.requeue_stuck_jobs",
            "schedule": 10 * 60,
            "kwargs": {"stale_after_minutes": 60},
        },
        # Retire LinkedIn postings the daily crawl hasn't seen in 21 days.
        # After the 06:00 crawl, so today's sightings count.
        "deactivate-stale-linkedin-daily": {
            "task": "app.tasks.job_tasks.deactivate_stale_jobs",
            "schedule": crontab(hour=6, minute=45),
            "kwargs": {"source": "linkedin", "max_age_days": 21},
        },
        # Walks the description backlog (rows never attempted). It was routed
        # but never scheduled, so it only ran if someone triggered it by hand.
        "backfill-descriptions-hourly": {
            "task": "app.tasks.job_tasks.backfill_descriptions",
            "schedule": 60 * 60,
            "kwargs": {"batch_size": 50},
        },
        # LinkedIn News: crawl top daily headlines at 07:00 UTC
        "scrape-linkedin-news-daily": {
            "task": "app.tasks.news_tasks.scrape_linkedin_news",
            "schedule": crontab(hour=7, minute=0),
        },
    },
)