"""
Message Service

Business logic for message operations.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.message import MessageRepository
from app.repositories.conversation import ConversationRepository
from app.models.message import Message, MessageRole


class MessageService(BaseService):
    """
    Message service.

    Handles message business logic and operations.
    """

    def __init__(self, db: AsyncSession = None):
        """Initialize message service."""
        super().__init__(db)
        # Initialize repos immediately if DB is provided
        if self.db:
            self.repo = MessageRepository(self.db)
            self.conversation_repo = ConversationRepository(self.db)
        else:
            self.repo = None
            self.conversation_repo = None

    async def __aenter__(self):
        """Enter async context."""
        await super().__aenter__()
        self.repo = MessageRepository(self.db)
        self.conversation_repo = ConversationRepository(self.db)
        return self

    async def add_message(
        self,
        conversation_id: int,
        role: MessageRole,
        content: str,
        agent_name: str = None,
        intent: str = None,
        sentiment: str = None,
        confidence_score: int = None
    ) -> Message:
        """
        Add message to conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role
            content: Message content
            agent_name: AI agent name (if role=AGENT)
            intent: Detected intent
            sentiment: Message sentiment
            confidence_score: Confidence score (0-100)

        Returns:
            Message: Created message

        Raises:
            ValueError: If conversation not found
        """
        # [SAFETY CHECK] Ensure repo is initialized
        if not self.conversation_repo or not self.repo:
            raise RuntimeError("Service not initialized. Use 'async with' or provide db session.")


        # Verify conversation exists
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create message
        data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "agent_name": agent_name,
            "intent": intent,
            "sentiment": sentiment,
            "confidence_score": confidence_score,
        }

        message = await self.repo.create(data)

        # Update conversation message count
        conversation.add_message()

        await self.commit()

        return message

    async def get_conversation_messages(
        self,
        conversation_id: int,
        page: int = 1,
        page_size: int = 100
    ) -> List[Message]:
        """
        Get messages for conversation.

        Args:
            conversation_id: Conversation ID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[Message]: Conversation messages
        """
        skip = (page - 1) * page_size
        return await self.repo.get_by_conversation(
            conversation_id,
            skip=skip,
            limit=page_size
        )
