"""
Test Fixtures fuer PVE Commander Backend

Stellt Test-Datenbank, Sessions und Mock-User bereit.
"""
import os
import sys

# WICHTIG: Environment Variables MUESSEN vor App-Imports gesetzt werden
os.environ.setdefault("DATA_DIR", "/tmp/pve-commander-test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DEBUG", "false")

import asyncio
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.auth.security import get_password_hash


# In-Memory SQLite fuer Tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Event-Loop fuer async Tests (session-scoped)"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Async Engine fuer Test-Datenbank"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async Session fuer Tests"""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
async def override_get_db(test_engine):
    """Override fuer get_db Dependency"""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _override_get_db():
        async with async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

    return _override_get_db


@pytest.fixture(scope="function")
async def client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """HTTP Client fuer API-Tests"""
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> User:
    """Erstellt einen Super-Admin User fuer Tests"""
    user = User(
        username="testadmin",
        password_hash=get_password_hash("testpassword123"),
        email="admin@test.local",
        is_admin=True,
        is_super_admin=True,
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def regular_user(test_session: AsyncSession) -> User:
    """Erstellt einen normalen User fuer Tests"""
    user = User(
        username="testuser",
        password_hash=get_password_hash("userpassword123"),
        email="user@test.local",
        is_admin=False,
        is_super_admin=False,
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def inactive_user(test_session: AsyncSession) -> User:
    """Erstellt einen inaktiven User fuer Tests"""
    user = User(
        username="inactiveuser",
        password_hash=get_password_hash("inactivepass123"),
        email="inactive@test.local",
        is_admin=False,
        is_super_admin=False,
        is_active=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """JWT Token fuer Admin-User"""
    from app.auth.security import create_access_token
    return create_access_token(data={"sub": admin_user.username})


@pytest.fixture
def user_token(regular_user: User) -> str:
    """JWT Token fuer regulaeren User"""
    from app.auth.security import create_access_token
    return create_access_token(data={"sub": regular_user.username})


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    """Authorization Headers mit Admin-Token"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_auth_headers(user_token: str) -> dict:
    """Authorization Headers mit User-Token"""
    return {"Authorization": f"Bearer {user_token}"}
