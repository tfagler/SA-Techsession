import hashlib
import logging
import os
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models import FetchCache


logger = logging.getLogger(__name__)
settings = get_settings()


def _cache_file_path(url: str) -> str:
    key = hashlib.sha256(url.encode('utf-8')).hexdigest()
    cache_dir = os.path.join(settings.docs_dir, 'fetch_cache')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f'{key}.bin')


def _read_cached_binary(url: str) -> bytes | None:
    path = _cache_file_path(url)
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return f.read()


def _write_cached_binary(url: str, body: bytes) -> None:
    path = _cache_file_path(url)
    with open(path, 'wb') as f:
        f.write(body)


async def fetch_with_cache(db: AsyncSession, url: str, expect_binary: bool = False) -> dict:
    result = await db.execute(select(FetchCache).where(FetchCache.url == url))
    cache = result.scalar_one_or_none()

    headers = {}
    cached_binary = _read_cached_binary(url)
    if cache and not expect_binary and cache.etag:
        headers['If-None-Match'] = cache.etag
    if cache and not expect_binary and cache.last_modified:
        headers['If-Modified-Since'] = cache.last_modified
    if cache and expect_binary and cached_binary is not None:
        # Only safe to send conditionals for binary when local bytes can satisfy 304.
        if cache.etag:
            headers['If-None-Match'] = cache.etag
        if cache.last_modified:
            headers['If-Modified-Since'] = cache.last_modified

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        logger.info(
            'fetch url=%s status=%d cached_binary_used=%s retry_happened=%s',
            url,
            response.status_code,
            False,
            False,
        )

    if response.status_code == 304 and cache:
        if expect_binary and cached_binary is not None:
            logger.info(
                'fetch url=%s status=304 cached_binary_used=%s retry_happened=%s',
                url,
                True,
                False,
            )
            return {
                'unchanged': True,
                'text': None,
                'binary': cached_binary,
                'etag': cache.etag,
                'last_modified': cache.last_modified,
                'content_hash': cache.response_hash,
                'mime_type': None,
            }
        if expect_binary and cached_binary is None:
            retry_headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                retry_resp = await client.get(url, headers=retry_headers)
            logger.info(
                'fetch url=%s status=%d cached_binary_used=%s retry_happened=%s',
                url,
                retry_resp.status_code,
                False,
                True,
            )
            retry_resp.raise_for_status()
            body_bytes = retry_resp.content
            body_text = retry_resp.text
            body_hash = hashlib.sha256(body_bytes).hexdigest()
            if body_bytes:
                _write_cached_binary(url, body_bytes)
            if cache:
                cache.etag = retry_resp.headers.get('ETag')
                cache.last_modified = retry_resp.headers.get('Last-Modified')
                cache.response_hash = body_hash
                cache.updated_at = datetime.utcnow()
            await db.commit()
            return {
                'unchanged': False,
                'text': body_text,
                'binary': body_bytes,
                'etag': retry_resp.headers.get('ETag'),
                'last_modified': retry_resp.headers.get('Last-Modified'),
                'content_hash': body_hash,
                'mime_type': retry_resp.headers.get('Content-Type'),
            }
        cached_text = cached_binary.decode('utf-8', errors='ignore') if cached_binary else None
        return {
            'unchanged': True,
            'text': cached_text,
            'binary': cached_binary,
            'etag': cache.etag,
            'last_modified': cache.last_modified,
            'content_hash': cache.response_hash,
            'mime_type': None,
        }

    response.raise_for_status()
    body_bytes = response.content
    body_text = response.text
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    if body_bytes:
        _write_cached_binary(url, body_bytes)

    if cache:
        cache.etag = response.headers.get('ETag')
        cache.last_modified = response.headers.get('Last-Modified')
        cache.response_hash = body_hash
        cache.updated_at = datetime.utcnow()
    else:
        cache = FetchCache(
            url=url,
            etag=response.headers.get('ETag'),
            last_modified=response.headers.get('Last-Modified'),
            response_hash=body_hash,
            updated_at=datetime.utcnow(),
        )
        db.add(cache)

    await db.commit()

    return {
        'unchanged': False,
        'text': body_text,
        'binary': body_bytes,
        'etag': response.headers.get('ETag'),
        'last_modified': response.headers.get('Last-Modified'),
        'content_hash': body_hash,
        'mime_type': response.headers.get('Content-Type'),
    }
