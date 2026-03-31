import pytest
import subprocess
import sys
import os
from sqlalchemy import text
from app.database import engine, Base
from dotenv import load_dotenv
load_dotenv()
import pytest_asyncio
os.environ["REDIS_URL"] = "redis://localhost:6379/1"


@pytest.fixture(scope="session", autouse=True)
async def enterprise_database_setup():
    """
    Enterprise Self-Healing Database Setup.
    """
    try:
        async with engine.begin() as conn:
            # 1. Ensure the vector extension exists for RAG
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            # 2. Build tables safely
            await conn.run_sync(Base.metadata.create_all)

            # 3. Check if a previous test batch wiped our data
            result = await conn.execute(text("SELECT COUNT(*) FROM customers"))
            customer_count = result.scalar()

        # 4. Self-Heal if the database is empty!
        if customer_count == 0:
            print("\n" + "=" * 60)
            print("⚠️ WARNING: Database is empty! Self-healing the environment...")

            # Re-seed basic data (Customers, Products, etc.)
            subprocess.run(
                [sys.executable, "-m", "app.seed_database"],
                env=os.environ.copy(),
                check=True,
            )

            # 📄 CRITICAL FIX: Re-ingest the RAG PDF data!
            if os.path.exists("ingest.py"):
                print("📄 Restoring RAG Document Vectors...")
                subprocess.run(
                    [sys.executable, "ingest.py"], env=os.environ.copy(), check=True
                )

            print(
                "✅ Database successfully self-healed. Starting tests...\n"
                + "=" * 60
                + "\n"
            )

        yield  # 🚀 The actual tests execute here!

    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def nuke_redis_cache(general_agent):
    """
    Runs BEFORE every single test to guarantee a completely empty cache.
    """
    if hasattr(general_agent, "cache_service") and hasattr(general_agent.cache_service, "redis_client"):
        # Ruthlessly wipe the current Redis logical database
        await general_agent.cache_service.redis_client.flushdb()

    yield # Execute the test in a completely clean state
