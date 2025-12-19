"""
Pytest Configuration and Fixtures

This module provides test configuration and reusable fixtures
for all test modules.
"""
import pytest_asyncio
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient

from app.main import app
from app.database import Base
from app.config import settings

# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

# Use async event loop for all tests
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an instance of the default event loop for the test session.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """
    Create test database engine.
    Uses separate test database to avoid affecting development data.
    """
    # Use test database URL (ensure this replaces the DB name correctly)
    # This replaces 'fca_support' with 'fca_support_test' in the connection string
    test_db_url = settings.database_url.replace("fca_support", "fca_support_test")

    # Create test engine
    engine = create_async_engine(
        test_db_url,
        echo=False,  # Don't log SQL in tests
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) # Start clean
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session for testing.

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
        await session.rollback()

    # CRITICAL FIX: Clean up data after each test
    # Because service methods call .commit(), data persists even after session.rollback()
    # We must explicitly delete data to prevent "already exists" errors in subsequent tests
    async with test_engine.begin() as conn:
        # Delete data from all tables in reverse order of dependency
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ============================================================================
# APPLICATION FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def client():
    """
    Create an async test client for testing FastAPI endpoints.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def anyio_backend():
    """
    Specify async backend for anyio.
    """
    return "asyncio"
