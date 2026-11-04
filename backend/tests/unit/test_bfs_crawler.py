import pytest

from app.scraping.bfs_crawler import BFSNewsCrawler, CrawlConfig


@pytest.mark.unit
def test_filter_links_requires_a_dot_boundary():
    crawler = BFSNewsCrawler(
        CrawlConfig(seed_url="https://example.com/", allowed_host_suffix="example.com")
    )
    kept = crawler._filter_links(
        [
            "https://example.com/news/a",
            "https://blog.example.com/news/b",
            "https://evilexample.com/news/c",      # suffix match, different site
            "https://example.com.evil.net/news/d",
        ],
        current_depth=0,
    )
    assert kept == ["https://example.com/news/a", "https://blog.example.com/news/b"]
