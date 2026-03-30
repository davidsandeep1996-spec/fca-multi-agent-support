import pytest
import sys
import os
import subprocess
from sqlalchemy import text
import app.models  # CRITICAL: Registers all tables in SQLAlchemy's memory
from app.database import engine, Base

@pytest.fixture(scope="session", autouse=True)
async def ensure_database_exists():
    """
    Enterprise Self-Healing Database Setup.
    Runs automatically before EVERY pytest command in your CI pipeline.
    It ensures tables exist AND ensures the seed data hasn't been deleted.
    """
    try:
        async with engine.begin() as conn:
            # 1. Ensure the vector extension exists for RAG
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            # 2. Build tables safely (skips if they already exist)
            await conn.run_sync(Base.metadata.create_all)

            # 3. The Enterprise Check: Did a previous test batch wipe the data?
            result = await conn.execute(text("SELECT COUNT(*) FROM customers"))
            customer_count = result.scalar()

        # 4. Self-Heal if the database is empty!
        if customer_count == 0:
            print("\n⚠️ WARNING: Database is empty! A previous test batch likely wiped the data.")
            print("🔄 Running seed_database.py to self-heal the environment...\n")

            # Run the seed script securely as a subprocess
            subprocess.run(
                [sys.executable, "-m", "app.seed_database"],
                env=os.environ.copy(),
                check=True
            )

        yield  # The tests execute here!

    finally:
        # We explicitly DO NOT run drop_all() here to preserve data for the next batch.
        await engine.dispose()
