from datetime import timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.core.datetime_utils import utc_now, utc_today_start
from app.models.news import NewsArticle
from app.tasks.news_tasks import parse_google_news_rss, purge_old_news


@pytest.mark.unit
def test_parse_google_news_rss_keeps_today_and_drops_previous_days():
    now = utc_now()
    yesterday = now - timedelta(days=2)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Today AI Chip Breakthrough - TechPub</title>
          <link>https://news.google.com/rss/articles/today-1</link>
          <pubDate>{format_datetime(now)}</pubDate>
          <source url="https://techpub.example">TechPub</source>
          <description>&lt;p&gt;Major datacenter expansion announced.&lt;/p&gt;</description>
        </item>
        <item>
          <title>Wordle today: The answer and hints - PuzzleSite</title>
          <link>https://news.google.com/rss/articles/noise-1</link>
          <pubDate>{format_datetime(now)}</pubDate>
          <source url="https://puzzlesite.example">PuzzleSite</source>
          <description>Daily puzzle hints.</description>
        </item>
        <item>
          <title>Old Yesterday Story - OldPub</title>
          <link>https://news.google.com/rss/articles/old-1</link>
          <pubDate>{format_datetime(yesterday)}</pubDate>
          <source url="https://oldpub.example">OldPub</source>
          <description>Yesterday headline.</description>
        </item>
      </channel>
    </rss>
    """
    items = parse_google_news_rss(xml, today_start=utc_today_start(), limit=10)
    assert len(items) == 1
    assert items[0]["title"] == "Today AI Chip Breakthrough - TechPub"
    assert items[0]["link"] == "https://news.google.com/rss/articles/today-1"


@pytest.mark.integration
async def test_news_allows_regular_user_url_submit_and_only_serves_today(
    client: AsyncClient, auth_headers, mock_db_session
):
    today_article = NewsArticle(
        url="https://example.com/today",
        url_sha256="a" * 64,
        title="Today Headline",
        source_domain="example.com",
        scraped_at=utc_now(),
    )
    yesterday_article = NewsArticle(
        url="https://example.com/old",
        url_sha256="b" * 64,
        title="Yesterday Headline",
        source_domain="example.com",
        scraped_at=utc_today_start() - timedelta(hours=2),
    )
    mock_db_session.add(today_article)
    mock_db_session.add(yesterday_article)
    await mock_db_session.commit()

    res = await client.get("/api/v1/news/", cookies=auth_headers["cookies"])
    assert res.status_code == 200
    titles = [a["title"] for a in res.json()]
    assert titles == ["Today Headline"]

    # Purge removes old-day rows cleanly.
    deleted = await purge_old_news(mock_db_session, utc_today_start())
    assert deleted == 1
    remaining = (await mock_db_session.execute(select(NewsArticle))).scalars().all()
    assert [r.title for r in remaining] == ["Today Headline"]

    # Regular authenticated user can submit a custom article URL.
    fake_task = MagicMock(id="task-news-user-1")
    with patch("app.api.v1.news.validate_crawl_url", return_value="https://example.com/article"), patch(
        "app.api.v1.news.crawl_news_site.delay", return_value=fake_task
    ):
        post_res = await client.post(
            "/api/v1/news/scrape?url=https://example.com/article",
            cookies=auth_headers["cookies"],
            headers=auth_headers["headers"],
        )
    assert post_res.status_code == 202
    assert post_res.json()["task_id"] == "task-news-user-1"

    # Manual LinkedIn refresh endpoint was removed.
    old_refresh = await client.post(
        "/api/v1/news/scrape/linkedin",
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert old_refresh.status_code in (404, 405)
