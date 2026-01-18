"""
FAQ Service
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base import BaseService
from app.repositories.faq import FAQRepository
from app.models.faq import FAQ

class FAQService(BaseService):
    def __init__(self, db: AsyncSession = None):
        super().__init__(db)
        if self.db:
            self.repo = FAQRepository(self.db)

    async def __aenter__(self):
        await super().__aenter__()
        self.repo = FAQRepository(self.db)
        return self

    async def search_faqs(self, query: str) -> List[FAQ]:
        """Search for relevant FAQs."""
        return await self.repo.search(query)
