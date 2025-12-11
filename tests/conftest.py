"""
Pytest Configuration and Fixtures

This module provides test configuration and reusable fixtures
for all test modules.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient

from app.main import app
from app.database import Base, get_db
from app.config import settings

# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

# Use async event loop for all tests
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an instance of the default event loop for the test session.

    Yields:
        AbstractEventLoop: Event loop
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
async def test_engine():
    """
    Create test database engine.

    Uses separate test database to avoid affecting development data.

    Yields:
        Engine: SQLAlchemy async engine
    """
    # Use test database URL
    test_db_url = settings.database_url.replace("/fca_support", "/fca_support_test")

    # Create test engine
    engine = create_async_engine(
        test_db_url,
        echo=False,  # Don't log SQL in tests
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session for testing.

    Each test gets a fresh session with transaction rollback after test.

    Args:
        test_engine: Test database engine

    Yields:
        AsyncSession: Database session
    """
    # Create session maker
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()  # Rollback after test


# ============================================================================
# APPLICATION FIXTURES
# ============================================================================

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create test client for FastAPI application.

    Overrides database dependency to use test database.

    Args:
        db_session: Test database session

    Yields:
        AsyncClient: HTTP client for testing
    """
    # Override database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Create test client
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    # Clear overrides
    app.dependency_overrides.clear()


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def anyio_backend():
    """
    Specify async backend for anyio.

    Returns:
        str: Backend name
    """
    return "asyncio"
