"""
FAQ Repository
"""
from typing import List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.faq import FAQ
from app.repositories.base import BaseRepository

class FAQRepository(BaseRepository[FAQ]):
    def __init__(self, db: AsyncSession):
        super().__init__(FAQ, db)

    async def search(self, query_text: str) -> List[FAQ]:
        """Simple keyword search."""
        # Clean the query for basic matching
        term = f"%{query_text}%"

        result = await self.db.execute(
            select(FAQ)
            .where(
                or_(
                    FAQ.question.ilike(term),
                    FAQ.keywords.ilike(term),
                    FAQ.category.ilike(term)
                )
            )
            .where(FAQ.is_active == True)
        )
        return result.scalars().all()
