"""
Base Service

Provides common service functionality.
All model-specific services should inherit from this.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal


class BaseService:
    """
    Base service class.

    Provides database session management and common functionality.
    """

    def __init__(self, db: AsyncSession = None):
        """
        Initialize service.

        Args:
            db: Optional database session (created if not provided)
        """
        self.db = db
        self._owns_session = db is None

    async def __aenter__(self):
        """Enter async context."""
        if self._owns_session:
            self.db = AsyncSessionLocal()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self._owns_session and self.db:
            if exc_type is not None:
                await self.db.rollback()
            await self.db.close()

    async def commit(self):
        """Commit current transaction."""
        await self.db.commit()

    async def rollback(self):
        """Rollback current transaction."""
        await self.db.rollback()
