import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.models import StudySession, User
from app.security import hash_password
from app.tasks import _run_ingest_once


@pytest.mark.asyncio
async def test_run_ingest_once_creates_isolated_session_context(monkeypatch):
    db_url = 'sqlite+aiosqlite:///./test.db'
    monkeypatch.setattr('app.tasks.settings.database_url', db_url)

    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as db:
        user = User(email='looptest@example.com', password_hash=hash_password('password123'))
        db.add(user)
        await db.flush()
        session = StudySession(user_id=user.id, title='Loop Safety', description='test')
        db.add(session)
        await db.commit()
        session_id = session.id
        user_id = user.id

    calls = {'count': 0}

    async def fake_ingest(db, user, sid):
        calls['count'] += 1
        row = await db.execute(select(StudySession).where(StudySession.id == sid))
        assert row.scalar_one_or_none() is not None

    monkeypatch.setattr('app.tasks.ingest_session', fake_ingest)

    await _run_ingest_once(session_id, user_id)
    await _run_ingest_once(session_id, user_id)
    assert calls['count'] == 2

    await engine.dispose()
