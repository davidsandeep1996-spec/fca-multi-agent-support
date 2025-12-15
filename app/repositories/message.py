"""
Message Repository

Data access layer for Message model.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Message repository."""

    def __init__(self, db: AsyncSession):
        """Initialize message repository."""
        super().__init__(Message, db)

    async def get_by_conversation(
        self,
        conversation_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """
        Get messages for conversation.

        Args:
            conversation_id: Conversation ID
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Message]: Conversation messages
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .offset(skip)
            .limit(limit)
            .order_by(Message.created_at.asc())  # Chronological order
        )
        return result.scalars().all()

    async def get_requiring_human(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """
        Get messages requiring human intervention.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Message]: Messages needing human
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.requires_human == True)
            .offset(skip)
            .limit(limit)
            .order_by(Message.created_at.asc())  # Oldest first
        )
        return result.scalars().all()
