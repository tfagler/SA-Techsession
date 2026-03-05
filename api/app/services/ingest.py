import asyncio
import hashlib
import io
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, urlunparse
from urllib import robotparser
import feedparser
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import Chunk, Highlight, Source, StudySession, User
from app.services.education import generate_education
from app.services.embeddings import embed_text
from app.services.fetcher import fetch_with_cache
from app.services.text_cleaning import clean_text, is_quality_chunk


logger = logging.getLogger(__name__)
settings = get_settings()


def _chunk_text(text: str, chunk_size: int = 900) -> list[str]:
    text = clean_text(text)
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size) if text[i:i + chunk_size]]


async def maybe_enqueue_refresh(session: StudySession, enqueue_fn, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    stale = not session.last_opened_at or (now - session.last_opened_at) >= timedelta(days=7)
    session.last_opened_at = now
    if stale and session.ingest_status not in {'queued', 'running'}:
        session.ingest_status = 'queued'
        session.ingest_error = None
        enqueue_fn(session.id)
    return stale


def _extract_html_text(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.find('title')
    h_tag = soup.find(['h1', 'h2'])
    paragraphs = ' '.join(p.get_text(' ', strip=True) for p in soup.find_all('p'))
    text = paragraphs or soup.get_text(' ', strip=True)
    title = title_tag.get_text(strip=True) if title_tag else ''
    header = h_tag.get_text(strip=True) if h_tag else 'Main Content'
    return text, title, header


def _normalize_url(url: str, keep_query: bool = False) -> str:
    parsed = urlparse(url)
    query = parsed.query if keep_query else ''
    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path or '/', '', query, ''))
    return normalized


def _extract_links(base_url: str, html: str, max_links: int) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    links: list[str] = []
    for a in soup.find_all('a', href=True):
        candidate = urljoin(base_url, a['href'])
        links.append(candidate)
        if len(links) >= max_links:
            break
    return links


def _source_domain(url: str) -> str:
    return urlparse(url).netloc


def _parse_crawl_config(source: Source) -> dict:
    cfg = source.crawl_config or {}
    allowed_default = [_source_domain(source.url or '')] if source.url else []
    allowed_domains = cfg.get('allowed_domains')
    if not isinstance(allowed_domains, list) or not allowed_domains:
        if settings.crawl_allowed_domains.strip():
            allowed_domains = [d.strip() for d in settings.crawl_allowed_domains.split(',') if d.strip()]
        else:
            allowed_domains = allowed_default

    return {
        'crawl_depth': int(cfg.get('crawl_depth', settings.crawl_depth)),
        'max_pages': int(cfg.get('max_pages', settings.crawl_max_pages)),
        'max_links_per_page': int(cfg.get('max_links_per_page', settings.crawl_max_links_per_page)),
        'allowed_domains': allowed_domains,
        'include_pdfs': bool(cfg.get('include_pdfs', settings.crawl_include_pdfs)),
        'include_paths': str(cfg.get('include_paths', settings.crawl_include_paths or '')),
        'exclude_paths': str(cfg.get('exclude_paths', settings.crawl_exclude_paths or '')),
        'respect_robots': bool(cfg.get('respect_robots', settings.crawl_respect_robots)),
        'concurrency': max(1, int(cfg.get('concurrency', settings.crawl_concurrency))),
        'request_delay_ms': max(0, int(cfg.get('request_delay_ms', settings.crawl_request_delay_ms))),
    }


def _link_filter_reason(
    start_url: str,
    normalized_url: str,
    visited: set[str],
    queued: set[str],
    allowed_domains: set[str],
    include_paths_re: re.Pattern | None,
    exclude_paths_re: re.Pattern | None,
    include_pdfs: bool,
) -> str | None:
    parsed = urlparse(normalized_url)
    if parsed.netloc not in allowed_domains:
        return 'external_domain'
    if normalized_url in visited or normalized_url in queued:
        return 'already_seen'
    if exclude_paths_re and exclude_paths_re.search(parsed.path):
        return 'excluded_pattern'
    if include_paths_re and not include_paths_re.search(parsed.path):
        return 'not_included_pattern'
    if parsed.path.lower().endswith('.pdf') and not include_pdfs:
        return 'pdf_excluded'
    if normalized_url == _normalize_url(start_url):
        return None
    return None


def _robots_allowed(url: str, robots_cache: dict[str, robotparser.RobotFileParser]) -> bool:
    parsed = urlparse(url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    if base not in robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(f'{base}/robots.txt')
        try:
            rp.read()
        except Exception:
            pass
        robots_cache[base] = rp
    try:
        return robots_cache[base].can_fetch('*', url)
    except Exception:
        return True


def _extract_pdf_text_from_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [clean_text(page.extract_text() or '') for page in reader.pages]
    return '\n'.join(p for p in pages if p)


def _extract_pdf_text_from_file(path: str) -> str:
    reader = PdfReader(path)
    pages = [clean_text(page.extract_text() or '') for page in reader.pages]
    return '\n'.join(p for p in pages if p)


async def _crawl_site_documents(db: AsyncSession, start_url: str, crawl_cfg: dict) -> tuple[list[dict], dict]:
    visited: set[str] = set()
    queued: set[str] = set()
    queue: list[tuple[str, int]] = [(_normalize_url(start_url), 0)]
    queued.add(_normalize_url(start_url))

    include_paths_re = re.compile(crawl_cfg['include_paths']) if crawl_cfg['include_paths'] else None
    exclude_paths_re = re.compile(crawl_cfg['exclude_paths']) if crawl_cfg['exclude_paths'] else None
    allowed_domains = set(crawl_cfg['allowed_domains'])
    robots_cache: dict[str, robotparser.RobotFileParser] = {}

    docs: list[dict] = []
    stats = {
        'pages_fetched': 0,
        'pages_skipped': 0,
        'pdfs_fetched': 0,
        'links_discovered': 0,
        'skip_reasons': defaultdict(int),
        'last_url': None,
    }

    semaphore = asyncio.Semaphore(crawl_cfg['concurrency'])

    async def fetch_one(url: str, depth: int) -> tuple[str, int, dict | None, str | None]:
        async with semaphore:
            if crawl_cfg['respect_robots'] and not _robots_allowed(url, robots_cache):
                return url, depth, None, 'robots_blocked'
            fetched = await fetch_with_cache(db, url, expect_binary=url.lower().endswith('.pdf'))
            if crawl_cfg['request_delay_ms'] > 0:
                await asyncio.sleep(crawl_cfg['request_delay_ms'] / 1000.0)
            return url, depth, fetched, None

    while queue and len(visited) < crawl_cfg['max_pages']:
        current_depth = queue[0][1]
        batch: list[tuple[str, int]] = []
        while queue and queue[0][1] == current_depth and len(batch) < crawl_cfg['concurrency'] * 2:
            batch.append(queue.pop(0))

        results = await asyncio.gather(*[fetch_one(url, depth) for url, depth in batch], return_exceptions=True)

        for item in results:
            if isinstance(item, Exception):
                stats['pages_skipped'] += 1
                stats['skip_reasons']['fetch_exception'] += 1
                continue

            url, depth, fetched, early_skip = item
            if url in visited:
                stats['pages_skipped'] += 1
                stats['skip_reasons']['already_seen'] += 1
                continue
            visited.add(url)
            stats['last_url'] = url

            if early_skip:
                stats['pages_skipped'] += 1
                stats['skip_reasons'][early_skip] += 1
                continue

            if not fetched:
                stats['pages_skipped'] += 1
                stats['skip_reasons']['no_fetch'] += 1
                continue

            mime_type = (fetched.get('mime_type') or '').lower()
            is_pdf = url.lower().endswith('.pdf') or 'application/pdf' in mime_type
            if is_pdf:
                if not fetched.get('binary'):
                    stats['pages_skipped'] += 1
                    stats['skip_reasons']['pdf_no_binary'] += 1
                    continue
                text = _extract_pdf_text_from_bytes(fetched['binary'])
                docs.append(
                    {
                        'url': url,
                        'title': url,
                        'header': 'PDF Document',
                        'content': text,
                        'content_type': 'pdf',
                        'mime_type': 'application/pdf',
                        'extract_method': 'pypdf',
                    }
                )
                stats['pages_fetched'] += 1
                stats['pdfs_fetched'] += 1
                continue

            html = fetched.get('text') or ''
            if not html:
                stats['pages_skipped'] += 1
                stats['skip_reasons']['non_html_or_empty'] += 1
                continue

            text, title, header = _extract_html_text(html)
            docs.append(
                {
                    'url': url,
                    'title': title or url,
                    'header': header,
                    'content': text,
                    'content_type': 'html',
                    'mime_type': fetched.get('mime_type') or 'text/html',
                    'extract_method': 'bs4',
                }
            )
            stats['pages_fetched'] += 1

            if depth >= crawl_cfg['crawl_depth']:
                continue

            links = _extract_links(url, html, crawl_cfg['max_links_per_page'])
            stats['links_discovered'] += len(links)
            for link in links:
                norm = _normalize_url(link)
                reason = _link_filter_reason(
                    start_url=start_url,
                    normalized_url=norm,
                    visited=visited,
                    queued=queued,
                    allowed_domains=allowed_domains,
                    include_paths_re=include_paths_re,
                    exclude_paths_re=exclude_paths_re,
                    include_pdfs=crawl_cfg['include_pdfs'],
                )
                if reason:
                    stats['pages_skipped'] += 1
                    stats['skip_reasons'][reason] += 1
                    continue
                queued.add(norm)
                queue.append((norm, depth + 1))

    stats['skip_reasons'] = dict(stats['skip_reasons'])
    return docs, stats


async def ingest_source(db: AsyncSession, source: Source) -> tuple[list[dict], dict]:
    source.status = 'processing'
    source.error = None
    await db.commit()

    try:
        crawl_stats = {
            'pages_fetched': 0,
            'pages_skipped': 0,
            'pdfs_fetched': 0,
            'links_discovered': 0,
            'skip_reasons': {},
            'last_url': source.url,
        }

        raw_docs: list[dict] = []

        if source.source_type in {'rss', 'url', 'pdf_url'}:
            if not source.url:
                raise ValueError('URL is required for this source type')

            if source.source_type == 'rss':
                fetched = await fetch_with_cache(db, source.url)
                parsed = feedparser.parse(fetched['text'] or '')
                entries = parsed.entries[:50]
                for e in entries:
                    raw_docs.append(
                        {
                            'url': source.url,
                            'title': getattr(e, 'title', '') or source.url,
                            'header': 'RSS Feed',
                            'content': f"{getattr(e, 'title', '')}\n{getattr(e, 'summary', '')}",
                            'content_type': 'text',
                            'mime_type': 'application/rss+xml',
                            'extract_method': 'feedparser',
                        }
                    )
                crawl_stats['pages_fetched'] = 1
            elif source.source_type == 'url':
                crawl_cfg = _parse_crawl_config(source)
                raw_docs, crawl_stats = await _crawl_site_documents(db, source.url, crawl_cfg)
            else:
                fetched = await fetch_with_cache(db, source.url, expect_binary=True)
                if not fetched['binary']:
                    raise ValueError('PDF URL returned no binary data')
                raw_docs.append(
                    {
                        'url': source.url,
                        'title': source.url,
                        'header': 'PDF URL document',
                        'content': _extract_pdf_text_from_bytes(fetched['binary']),
                        'content_type': 'pdf',
                        'mime_type': 'application/pdf',
                        'extract_method': 'pypdf',
                    }
                )
                crawl_stats['pages_fetched'] = 1
                crawl_stats['pdfs_fetched'] = 1
        elif source.source_type == 'pdf_upload':
            if not source.document_path:
                raise ValueError('No uploaded file path')
            raw_docs.append(
                {
                    'url': source.url,
                    'title': source.title or source.document_path.rsplit('/', 1)[-1],
                    'header': 'Uploaded PDF',
                    'content': _extract_pdf_text_from_file(source.document_path),
                    'content_type': 'pdf',
                    'mime_type': 'application/pdf',
                    'extract_method': 'pypdf',
                }
            )
            crawl_stats['pages_fetched'] = 1
            crawl_stats['pdfs_fetched'] = 1
        else:
            raise ValueError(f'Unsupported source type: {source.source_type}')

        content_text = '\n\n'.join(clean_text(d.get('content', '')) for d in raw_docs if d.get('content'))
        content_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest() if content_text else None

        if source.content_hash and content_hash and source.content_hash == content_hash:
            source.status = 'ready'
            source.last_ingested_at = datetime.utcnow()
            await db.commit()
            return [], crawl_stats

        source.content_hash = content_hash
        source.status = 'ready'
        source.last_ingested_at = datetime.utcnow()

        await db.execute(delete(Chunk).where(Chunk.source_id == source.id))

        valid_chunks: list[dict] = []
        for doc in raw_docs:
            citation_snippet = clean_text(doc.get('content', ''))[:280]
            for raw in _chunk_text(doc.get('content', '')):
                chunk = clean_text(raw)
                ok, _ = is_quality_chunk(chunk)
                if not ok:
                    continue
                valid_chunks.append(
                    {
                        'content': chunk,
                        'char_count': len(chunk),
                        'word_count': len(chunk.split()),
                        'source_type': doc.get('content_type') or 'text',
                        'content_type': doc.get('content_type') or 'text',
                        'mime_type': doc.get('mime_type') or 'text/plain',
                        'extract_method': doc.get('extract_method') or 'direct',
                        'source_url': doc.get('url') or source.url,
                        'title': doc.get('title') or source.title,
                        'citation_url': doc.get('url') or source.url,
                        'citation_title': doc.get('title') or source.title,
                        'citation_header': doc.get('header') or 'Main Content',
                        'citation_snippet': citation_snippet,
                        'fetched_at': datetime.utcnow(),
                    }
                )

        if not valid_chunks:
            raise ValueError('No high-quality readable chunks extracted from source')

        for c in valid_chunks:
            db.add(
                Chunk(
                    session_id=source.session_id,
                    source_id=source.id,
                    content=c['content'],
                    embedding=embed_text(c['content']),
                    source_type=c['source_type'],
                    content_type=c['content_type'],
                    mime_type=c['mime_type'],
                    extract_method=c['extract_method'],
                    source_url=c['source_url'],
                    title=c['title'],
                    fetched_at=c['fetched_at'],
                    char_count=c['char_count'],
                    word_count=c['word_count'],
                    citation_url=c['citation_url'],
                    citation_title=c['citation_title'],
                    citation_header=c['citation_header'],
                    citation_snippet=c['citation_snippet'],
                )
            )

        await db.commit()
        return valid_chunks, crawl_stats
    except Exception as exc:
        source.status = 'failed'
        source.error = str(exc)
        await db.commit()
        raise


async def ingest_session(db: AsyncSession, user: User, session_id: int) -> None:
    session_result = await db.execute(
        select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        return

    session.ingest_status = 'running'
    session.ingest_error = None
    session.education_error = None
    session.ingest_started_at = datetime.utcnow()
    session.ingest_finished_at = None
    session.pages_fetched = 0
    session.pages_skipped = 0
    session.pdfs_fetched = 0
    session.chunks_created = 0
    session.total_chars_indexed = 0
    session.ingest_last_url = None
    session.ingest_skip_reasons = {}
    await db.commit()

    try:
        result = await db.execute(
            select(Source).where(Source.session_id == session_id).order_by(Source.id.asc())
        )
        sources = result.scalars().all()
        all_chunks: list[str] = []
        first_citation = None
        skip_accumulator: defaultdict[str, int] = defaultdict(int)

        for source in sources:
            chunks, crawl_stats = await ingest_source(db, source)
            session.pages_fetched += int(crawl_stats.get('pages_fetched', 0))
            session.pages_skipped += int(crawl_stats.get('pages_skipped', 0))
            session.pdfs_fetched += int(crawl_stats.get('pdfs_fetched', 0))
            if crawl_stats.get('last_url'):
                session.ingest_last_url = crawl_stats.get('last_url')
            for reason, count in (crawl_stats.get('skip_reasons') or {}).items():
                skip_accumulator[reason] += int(count)

            for c in chunks:
                all_chunks.append(c['content'])
                session.chunks_created += 1
                session.total_chars_indexed += int(c.get('char_count', 0))
                if not first_citation:
                    first_citation = c

            session.ingest_skip_reasons = dict(skip_accumulator)
            await db.commit()

        if all_chunks:
            try:
                education = await generate_education(all_chunks, user=user)
            except Exception as exc:
                session.education_error = str(exc)
                raise
            session.education_summary = education.get('summary')
            session.education_key_points = education.get('key_points', [])
            session.education_glossary = education.get('glossary', {})
            session.education_quiz = education.get('quiz', [])

            await db.execute(delete(Highlight).where(Highlight.session_id == session.id, Highlight.user_id == user.id))
            citation = {
                'url': first_citation.get('citation_url') if first_citation else None,
                'title': first_citation.get('citation_title') if first_citation else None,
                'header': first_citation.get('citation_header') if first_citation else None,
                'snippet': first_citation.get('citation_snippet') if first_citation else None,
            }
            for point in (education.get('key_points') or [])[:4]:
                db.add(
                    Highlight(
                        session_id=session.id,
                        user_id=user.id,
                        text=point,
                        citation=citation,
                    )
                )

        session.ingest_status = 'done'
        session.ingest_finished_at = datetime.utcnow()
        logger.info(
            'ingest.summary session_id=%s total_pages=%s total_chunks=%s total_chars=%s skip_reasons=%s',
            session.id,
            session.pages_fetched,
            session.chunks_created,
            session.total_chars_indexed,
            session.ingest_skip_reasons,
        )
        await db.commit()
    except Exception as exc:
        session.ingest_status = 'failed'
        session.ingest_error = str(exc)
        session.ingest_finished_at = datetime.utcnow()
        await db.commit()
        raise
