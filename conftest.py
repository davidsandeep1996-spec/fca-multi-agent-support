import pytest_asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

# Forcefully silence Langfuse background logs
logging.getLogger("langfuse").setLevel(logging.CRITICAL)

@pytest_asyncio.fixture
async def db_session():
    """Single, isolated DB session for each test. Guaranteed to prevent loop mismatch."""
    # 1. Create engine inside the test's own loop
    engine = create_async_engine(settings.database_url, echo=False)

    # 2. Begin transaction
    async with engine.begin() as conn:
        session_maker = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint"
        )

        # 3. Yield session to the test
        async with session_maker() as session:
            yield session
            # 4. Rollback safely when test finishes
            await session.rollback()

    # 5. Destroy engine completely
    await engine.dispose()
