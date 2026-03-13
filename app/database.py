"""
Database Connection and Session Management

This module configures SQLAlchemy async engine and provides
database session management for the application.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text  # Add 'text' here

from typing import AsyncGenerator
import logging
from sqlalchemy.pool import NullPool
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE ENGINE
# ============================================================================

# Define base engine arguments
engine_kwargs = {
    "echo": settings.database_echo,
    "future": True,  # Ensures SQLAlchemy 2.0 standards
}

# Apply environment-specific configurations
if settings.environment == "test":
    # CRITICAL: Use NullPool in testing to prevent background tasks
    # from outliving the Pytest event loop.
    engine_kwargs.update(
        {
            "poolclass": NullPool,
            "echo": False,  # Prevent log flooding during high-volume AI tests
        }
    )
else:
    # Production/Development pooling configuration
    engine_kwargs.update(
        {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_recycle": 3600,
            "pool_pre_ping": True,  # Automatically reconnects dropped DB links
        }
    )

# Create the async engine dynamically
engine = create_async_engine(settings.database_url, **engine_kwargs)


# ============================================================================
# SESSION MAKER
# ============================================================================

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autocommit=False,  # Explicit commits only
    autoflush=False,  # Explicit flushes only
)


# ============================================================================
# BASE MODEL
# ============================================================================

# Declarative base for ORM models
Base = declarative_base()


# ============================================================================
# SESSION DEPENDENCY
# ============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency for FastAPI.

    Provides a database session for each request and ensures
    proper cleanup after the request completes.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Commit if no exceptions
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()  # Always close session


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


async def init_db() -> None:
    """
    Initialize database tables and extensions.
    """
    async with engine.begin() as conn:
        logger.info("Enabling pgvector extension")
        # [NEW] This MUST run before table creation to support Vector columns
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        logger.info("Creating database tables")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def close_db() -> None:
    """
    Close database connections.

    Should be called on application shutdown to properly
    close all database connections.
    """
    logger.info("Closing database connections")
    await engine.dispose()
    logger.info("Database connections closed")


# ============================================================================
# DATABASE HEALTH CHECK
# ============================================================================


async def check_db_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            # Simple query to test connection
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


# ============================================================================
# TESTING HELPER
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test_connection():
        """Test database connection."""
        print("Testing database connection...")

        # Test connection
        is_healthy = await check_db_connection()

        if is_healthy:
            print("✅ Database connection successful!")
        else:
            print("❌ Database connection failed!")

        # Close connections
        await close_db()

    # Run test
    asyncio.run(test_connection())
