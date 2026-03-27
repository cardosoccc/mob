"""Shared test fixtures."""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mob.models.base import Base

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_k8s_state(monkeypatch):
    """Prevent unit tests from hitting a live K8s cluster."""
    import mob.services.sessions as sess_mod
    sess_mod._k8s_custom_api = None
    sess_mod._k8s_core_api = None
    sess_mod._k8s_config_loaded = False
    monkeypatch.setattr(sess_mod, "_try_get_k8s_custom_api", lambda: None)
    monkeypatch.setattr(sess_mod, "_try_get_k8s_core_api", lambda: None)


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    from mob.api.app import create_app
    from mob.database import get_session

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
