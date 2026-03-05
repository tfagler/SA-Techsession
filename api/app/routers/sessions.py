from datetime import datetime
import os
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Highlight, Source, StudySession, User
from app.schemas import SessionCreateIn, SourceCreateIn
from app.services.ingest import maybe_enqueue_refresh


router = APIRouter(prefix='/sessions', tags=['sessions'])
settings = get_settings()


@router.post('')
async def create_session(payload: SessionCreateIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = StudySession(user_id=user.id, title=payload.title, description=payload.description, ingest_status='done')
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {'id': session.id, 'title': session.title, 'description': session.description, 'created_at': session.created_at}


@router.get('')
async def list_sessions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(StudySession).where(StudySession.user_id == user.id).order_by(StudySession.id.desc()))
    sessions = result.scalars().all()
    return [
        {
            'id': s.id,
            'title': s.title,
            'description': s.description,
            'ingest_status': s.ingest_status,
            'ingest_error': s.ingest_error,
            'pages_fetched': s.pages_fetched,
            'pages_skipped': s.pages_skipped,
            'pdfs_fetched': s.pdfs_fetched,
            'chunks_created': s.chunks_created,
            'total_chars_indexed': s.total_chars_indexed,
            'created_at': s.created_at,
        }
        for s in sessions
    ]


@router.get('/{session_id}')
async def get_session(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    def enqueue_fn(sid: int):
        celery_app.send_task('app.tasks.ingest_session_task', args=[sid, user.id])

    await maybe_enqueue_refresh(session, enqueue_fn, datetime.utcnow())
    await db.commit()

    source_result = await db.execute(select(Source).where(Source.session_id == session.id).order_by(Source.id.asc()))
    highlight_result = await db.execute(select(Highlight).where(Highlight.session_id == session.id).order_by(Highlight.id.desc()))

    return {
        'id': session.id,
        'title': session.title,
        'description': session.description,
        'ingest_status': session.ingest_status,
        'ingest_error': session.ingest_error,
        'ingest_started_at': session.ingest_started_at,
        'ingest_finished_at': session.ingest_finished_at,
        'pages_fetched': session.pages_fetched,
        'pages_skipped': session.pages_skipped,
        'pdfs_fetched': session.pdfs_fetched,
        'chunks_created': session.chunks_created,
        'total_chars_indexed': session.total_chars_indexed,
        'ingest_last_url': session.ingest_last_url,
        'ingest_skip_reasons': session.ingest_skip_reasons or {},
        'education_error': session.education_error,
        'education': {
            'summary': session.education_summary,
            'key_points': session.education_key_points or [],
            'glossary': session.education_glossary or {},
            'quiz': session.education_quiz or [],
        },
        'sources': [
            {
                'id': s.id,
                'source_type': s.source_type,
                'url': s.url,
                'title': s.title,
                'status': s.status,
                'error': s.error,
                'crawl_config': s.crawl_config,
            }
            for s in source_result.scalars().all()
        ],
        'highlights': [
            {'id': h.id, 'text': h.text, 'citation': h.citation, 'created_at': h.created_at}
            for h in highlight_result.scalars().all()
        ],
    }


@router.post('/{session_id}/sources')
async def add_source(session_id: int, payload: SourceCreateIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session_result = await db.execute(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail='Session not found')

    if payload.source_type in {'rss', 'url', 'pdf_url'} and not payload.url:
        raise HTTPException(status_code=400, detail='url required for rss/url/pdf_url')

    source = Source(
        session_id=session_id,
        source_type=payload.source_type,
        url=payload.url,
        status='pending',
        crawl_config=payload.crawl_config,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {
        'id': source.id,
        'source_type': source.source_type,
        'url': source.url,
        'status': source.status,
        'crawl_config': source.crawl_config,
    }


@router.post('/{session_id}/upload-pdf')
async def upload_pdf(session_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail='Only PDF supported')

    session_result = await db.execute(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail='Session not found')

    os.makedirs(settings.docs_dir, exist_ok=True)
    path = os.path.join(settings.docs_dir, f"{uuid.uuid4()}-{file.filename}")
    body = await file.read()
    with open(path, 'wb') as f:
        f.write(body)

    source = Source(session_id=session_id, source_type='pdf_upload', document_path=path, title=file.filename, status='pending')
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {'id': source.id, 'source_type': source.source_type, 'title': source.title, 'status': source.status}


@router.post('/{session_id}/ingest')
async def trigger_ingest(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    session.ingest_status = 'queued'
    session.ingest_error = None
    await db.commit()
    celery_app.send_task('app.tasks.ingest_session_task', args=[session_id, user.id])
    return {'queued': True}
