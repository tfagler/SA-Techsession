import asyncio
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session', autouse=True)
async def setup_db():
    os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test.db'
    engine = create_async_engine('sqlite+aiosqlite:///./test.db', future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    engine = create_async_engine('sqlite+aiosqlite:///./test.db', future=True)
    TestSession = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
