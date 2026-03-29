import pytest
from sqlalchemy import text
import app.models  # CRITICAL: Registers all tables in SQLAlchemy's memory
from app.database import engine, Base

@pytest.fixture(scope="session", autouse=True)
async def ensure_database_exists():
    """
    Self-Healing Database Setup.
    Runs automatically before EVERY pytest command.
    It safely creates tables if they are missing, but preserves existing data.
    """
    try:
        async with engine.begin() as conn:
            # 1. Ensure the vector extension exists for RAG
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            # 2. Build tables safely.
            # create_all automatically skips tables that already exist!
            await conn.run_sync(Base.metadata.create_all)

        yield  # The tests execute here!

    finally:
        # We explicitly DO NOT run drop_all() here.
        # We want the tables (and seed data) to survive for the next pytest command in CI.
        await engine.dispose()
