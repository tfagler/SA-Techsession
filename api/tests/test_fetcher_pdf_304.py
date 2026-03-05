import pytest
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base
from app.models import FetchCache
from app.services import fetcher


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b'', headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = content.decode('utf-8', errors='ignore') if content else ''

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request('GET', 'http://example.com')
            resp = httpx.Response(self.status_code, request=req, content=self.content)
            raise httpx.HTTPStatusError('error', request=req, response=resp)


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], calls: list[dict]):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        self._calls.append({'url': url, 'headers': headers or {}})
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_pdf_fetch_200_content(tmp_path, monkeypatch):
    db_file = tmp_path / 'test1.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}', future=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(fetcher.settings, 'docs_dir', str(tmp_path))
    calls = []
    responses = [_FakeResponse(200, b'%PDF-1.4 test', {'ETag': 'abc'})]
    monkeypatch.setattr(fetcher.httpx, 'AsyncClient', lambda **kwargs: _FakeClient(responses, calls))

    async with Session() as db:
        out = await fetcher.fetch_with_cache(db, 'https://example.com/file.pdf', expect_binary=True)
        assert out['binary'] == b'%PDF-1.4 test'
        assert out['unchanged'] is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_fetch_304_uses_cached_binary(tmp_path, monkeypatch):
    db_file = tmp_path / 'test2.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}', future=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(fetcher.settings, 'docs_dir', str(tmp_path))
    url = 'https://example.com/file.pdf'

    async with Session() as db:
        db.add(FetchCache(url=url, etag='v1', last_modified='x', response_hash='h'))
        await db.commit()

    fetcher._write_cached_binary(url, b'cached pdf bytes')

    calls = []
    responses = [_FakeResponse(304, b'')]
    monkeypatch.setattr(fetcher.httpx, 'AsyncClient', lambda **kwargs: _FakeClient(responses, calls))

    async with Session() as db:
        out = await fetcher.fetch_with_cache(db, url, expect_binary=True)
        assert out['unchanged'] is True
        assert out['binary'] == b'cached pdf bytes'

    await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_fetch_304_without_cache_retries_no_cache_and_succeeds(tmp_path, monkeypatch):
    db_file = tmp_path / 'test3.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}', future=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(fetcher.settings, 'docs_dir', str(tmp_path))
    url = 'https://example.com/file.pdf'

    async with Session() as db:
        db.add(FetchCache(url=url, etag='v1', last_modified='x', response_hash='h'))
        await db.commit()

    calls = []
    responses = [
        _FakeResponse(304, b''),
        _FakeResponse(200, b'%PDF-1.4 refreshed', {'ETag': 'v2'}),
    ]
    monkeypatch.setattr(fetcher.httpx, 'AsyncClient', lambda **kwargs: _FakeClient(responses, calls))

    async with Session() as db:
        out = await fetcher.fetch_with_cache(db, url, expect_binary=True)
        assert out['unchanged'] is False
        assert out['binary'] == b'%PDF-1.4 refreshed'

    assert len(calls) == 2
    retry_headers = calls[1]['headers']
    assert retry_headers.get('Cache-Control') == 'no-cache'
    assert retry_headers.get('Pragma') == 'no-cache'

    await engine.dispose()
