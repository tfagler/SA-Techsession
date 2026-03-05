import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.celery_app import celery_app
from app.config import get_settings
from app.models import StudySession, User
from app.services.ingest import ingest_session


settings = get_settings()
logger = logging.getLogger(__name__)


async def _run_ingest_once(session_id: int, user_id: int) -> None:
    # Create async engine/session per task execution context to avoid cross-loop futures.
    engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return
            session_result = await db.execute(select(StudySession).where(StudySession.id == session_id))
            session = session_result.scalar_one_or_none()
            if not session:
                return
            await ingest_session(db, user, session_id)
    finally:
        await engine.dispose()


@celery_app.task(name='app.tasks.ingest_session_task')
def ingest_session_task(session_id: int, user_id: int):
    try:
        asyncio.run(_run_ingest_once(session_id, user_id))
    except Exception as exc:
        # Avoid unhandled exceptions at worker top-level; status/error are persisted in ingest service.
        logger.exception('ingest_session_task failed session_id=%s user_id=%s error=%s', session_id, user_id, exc)
