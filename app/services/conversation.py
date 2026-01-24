"""
Conversation Service

Business logic for conversation operations.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.conversation import ConversationRepository
from app.repositories.customer import CustomerRepository
from app.models.conversation import Conversation, ConversationStatus, ConversationChannel


class ConversationService(BaseService):
    """
    Conversation service.

    Handles conversation business logic and operations.
    """

    def __init__(self, db: AsyncSession = None):
        """Initialize conversation service."""
        super().__init__(db)
# 👇 THIS WAS LIKELY MISSING OR BROKEN 👇
        if self.db:
            self.repo = ConversationRepository(self.db)
            self.customer_repo = CustomerRepository(self.db)
        else:
            self.repo = None
            self.customer_repo = None

    async def __aenter__(self):
        """Enter async context."""
        await super().__aenter__()
        self.repo = ConversationRepository(self.db)
        self.customer_repo = CustomerRepository(self.db)
        return self

    async def start_conversation(
        self,
        customer_id: int,
        title: str,
        channel: ConversationChannel = ConversationChannel.WEB
    ) -> Conversation:
        """
        Start new conversation.

        Args:
            customer_id: Customer ID
            title: Conversation title
            channel: Communication channel

        Returns:
            Conversation: Created conversation

        Raises:
            ValueError: If customer not found
        """
        # Verify customer exists
        customer = await self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Create conversation
        data = {
            "customer_id": customer_id,
            "title": title,
            "channel": channel,
            "status": ConversationStatus.ACTIVE,
            "message_count": 0,
        }

        conversation = await self.repo.create(data)
        await self.commit()

        return conversation

    async def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """
        Get conversation by ID.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation or None: Conversation if found
        """
        return await self.repo.get_by_id(conversation_id)

    async def get_customer_conversations(
        self,
        customer_id: int,
        page: int = 1,
        page_size: int = 100
    ) -> List[Conversation]:
        """
        Get conversations for customer.

        Args:
            customer_id: Customer ID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[Conversation]: Customer conversations
        """
        skip = (page - 1) * page_size
        return await self.repo.get_by_customer(
            customer_id,
            skip=skip,
            limit=page_size
        )

    async def resolve_conversation(
        self,
        conversation_id: int,
        summary: str = None
    ) -> Optional[Conversation]:
        """
        Mark conversation as resolved.

        Args:
            conversation_id: Conversation ID
            summary: Resolution summary

        Returns:
            Conversation or None: Resolved conversation
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            return None

        conversation.mark_resolved(summary=summary)
        await self.commit()

        return conversation

    async def escalate_conversation(
        self,
        conversation_id: int,
        reason: str,
        priority: str,
        assigned_group: str = None,  # [FIX] New Arg
        ticket_id: str = None        # [FIX] New Arg
    ) -> Optional[Conversation]:
        """Escalate with full tracking details."""

        conversation = await self.repo.get_by_id(conversation_id)

        if conversation:
            # Pass all data to the model
            conversation.escalate(
                reason=reason,
                priority=priority,
                assigned_group=assigned_group,
                ticket_id=ticket_id
            )

            await self.repo.session.commit()
            await self.repo.session.refresh(conversation)

        return conversation
