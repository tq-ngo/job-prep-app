from celery.schedules import crontab

# This schedule is loaded by Celery Beat
# Format: "task_name": {"task": "...", "schedule": crontab(...)}

CELERYBEAT_SCHEDULE = {
    # Scrape Github every 6 hours
    "scrape-github-every-6h": {
        "task": "tasks.scrape_github",
        "schedule": crontab(minute=0, hour="*/6"),  # 00:00, 06:00, 12:00, 18:00
    },
    
    # Scrape We Work Remotely daily at 8am UTC
    "scrape-weworkremotely-daily": {
        "task": "tasks.scrape_weworkremotely",
        "schedule": crontab(minute=0, hour=8),
    },
    
    # Crawl tech news every 4 hours
    "crawl-techcrunch-every-4h": {
        "task": "tasks.crawl_news_site",
        "schedule": crontab(minute=30, hour="*/4"),
        "args": [{"seed_url": "https://techcrunch.com", "max_pages": 30}],
    },
    
    # Cleanup old dedup Redis keys daily at 2am
    "cleanup-dedup-daily": {
        "task": "tasks.cleanup_expired_dedup",
        "schedule": crontab(minute=0, hour=2),
    },
}