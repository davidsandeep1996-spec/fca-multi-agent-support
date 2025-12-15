"""
Conversation Repository

Data access layer for Conversation model.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Conversation repository."""

    def __init__(self, db: AsyncSession):
        """Initialize conversation repository."""
        super().__init__(Conversation, db)

    async def get_by_customer(
        self,
        customer_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Conversation]:
        """
        Get conversations for customer.

        Args:
            customer_id: Customer ID
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Conversation]: Customer conversations
        """
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.customer_id == customer_id)
            .offset(skip)
            .limit(limit)
            .order_by(Conversation.created_at.desc())
        )
        return result.scalars().all()

    async def get_active_conversations(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Conversation]:
        """
        Get active conversations.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Conversation]: Active conversations
        """
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.status == ConversationStatus.ACTIVE)
            .offset(skip)
            .limit(limit)
            .order_by(Conversation.updated_at.desc())
        )
        return result.scalars().all()

    async def get_escalated_conversations(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Conversation]:
        """
        Get escalated conversations.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Conversation]: Escalated conversations
        """
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.status == ConversationStatus.ESCALATED)
            .offset(skip)
            .limit(limit)
            .order_by(Conversation.updated_at.asc())  # Oldest first
        )
        return result.scalars().all()
