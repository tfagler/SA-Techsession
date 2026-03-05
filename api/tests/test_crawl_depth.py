import pytest
from app.services import ingest


@pytest.mark.asyncio
async def test_crawl_depth_0_only_seed(monkeypatch):
    site = {
        'https://example.com/': '<a href="/a">A</a><p>Home content that is long enough for extraction and testing.</p>',
        'https://example.com/a': '<p>Child page content long enough for extraction and testing.</p>',
    }

    async def fake_fetch(db, url, expect_binary=False):
        return {'text': site.get(url, ''), 'binary': None, 'mime_type': 'text/html'}

    monkeypatch.setattr(ingest, 'fetch_with_cache', fake_fetch)

    docs, stats = await ingest._crawl_site_documents(
        db=None,
        start_url='https://example.com/',
        crawl_cfg={
            'crawl_depth': 0,
            'max_pages': 50,
            'max_links_per_page': 50,
            'allowed_domains': ['example.com'],
            'include_pdfs': True,
            'include_paths': '',
            'exclude_paths': '',
            'respect_robots': False,
            'concurrency': 2,
            'request_delay_ms': 0,
        },
    )

    assert len(docs) == 1
    assert stats['pages_fetched'] == 1


@pytest.mark.asyncio
async def test_crawl_depth_2_includes_grandchildren(monkeypatch):
    site = {
        'https://example.com/': '<a href="/a">A</a><p>Home content that is long enough for extraction and testing.</p>',
        'https://example.com/a': '<a href="/b">B</a><p>Child page content long enough for extraction and testing.</p>',
        'https://example.com/b': '<p>Grandchild page content long enough for extraction and testing.</p>',
    }

    async def fake_fetch(db, url, expect_binary=False):
        return {'text': site.get(url, ''), 'binary': None, 'mime_type': 'text/html'}

    monkeypatch.setattr(ingest, 'fetch_with_cache', fake_fetch)

    docs, stats = await ingest._crawl_site_documents(
        db=None,
        start_url='https://example.com/',
        crawl_cfg={
            'crawl_depth': 2,
            'max_pages': 50,
            'max_links_per_page': 50,
            'allowed_domains': ['example.com'],
            'include_pdfs': True,
            'include_paths': '',
            'exclude_paths': '',
            'respect_robots': False,
            'concurrency': 2,
            'request_delay_ms': 0,
        },
    )

    fetched_urls = {d['url'] for d in docs}
    assert 'https://example.com/' in fetched_urls
    assert 'https://example.com/a' in fetched_urls
    assert 'https://example.com/b' in fetched_urls
    assert stats['pages_fetched'] >= 3


@pytest.mark.asyncio
async def test_crawl_depth_1_includes_direct_children_only(monkeypatch):
    site = {
        'https://example.com/': '<a href=\"/a\">A</a><p>Home content that is long enough for extraction and testing.</p>',
        'https://example.com/a': '<a href=\"/b\">B</a><p>Child page content long enough for extraction and testing.</p>',
        'https://example.com/b': '<p>Grandchild page content long enough for extraction and testing.</p>',
    }

    async def fake_fetch(db, url, expect_binary=False):
        return {'text': site.get(url, ''), 'binary': None, 'mime_type': 'text/html'}

    monkeypatch.setattr(ingest, 'fetch_with_cache', fake_fetch)

    docs, _ = await ingest._crawl_site_documents(
        db=None,
        start_url='https://example.com/',
        crawl_cfg={
            'crawl_depth': 1,
            'max_pages': 50,
            'max_links_per_page': 50,
            'allowed_domains': ['example.com'],
            'include_pdfs': True,
            'include_paths': '',
            'exclude_paths': '',
            'respect_robots': False,
            'concurrency': 2,
            'request_delay_ms': 0,
        },
    )

    fetched_urls = {d['url'] for d in docs}
    assert 'https://example.com/' in fetched_urls
    assert 'https://example.com/a' in fetched_urls
    assert 'https://example.com/b' not in fetched_urls


def test_normalize_url_keeps_distinct_paths_and_drops_fragment():
    assert ingest._normalize_url('https://example.com/a#x') == 'https://example.com/a'
    assert ingest._normalize_url('https://example.com/a') != ingest._normalize_url('https://example.com/b')
