"""
Conversation Model

Represents a conversation between a customer and the AI support system.
Links customers to messages and tracks conversation state.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, Index
from sqlalchemy.orm import relationship
from typing import List
import enum

from app.models import BaseModel


# ============================================================================
# ENUMS
# ============================================================================

class ConversationStatus(str, enum.Enum):
    """Conversation status enumeration."""

    ACTIVE = "active"          # Conversation ongoing
    RESOLVED = "resolved"      # Issue resolved
    ESCALATED = "escalated"    # Escalated to human agent
    CLOSED = "closed"          # Conversation closed


class ConversationChannel(str, enum.Enum):
    """Conversation channel enumeration."""

    WEB = "web"                # Web chat
    MOBILE = "mobile"          # Mobile app
    API = "api"                # API integration
    WHATSAPP = "whatsapp"      # WhatsApp integration
    SMS = "sms"                # SMS integration


# ============================================================================
# CONVERSATION MODEL
# ============================================================================

class Conversation(BaseModel):
    """
    Conversation model.

    Represents a conversation between a customer and the AI system.
    Contains conversation metadata, status, and relationships to
    customer and messages.
    """

    __tablename__ = "conversations"

    # ========================================================================
    # FOREIGN KEYS
    # ========================================================================

    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to customer",
    )

    # ========================================================================
    # CONVERSATION METADATA
    # ========================================================================

    title = Column(
        String(200),
        nullable=False,
        comment="Conversation title/subject",
    )

    status = Column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="Current conversation status",
    )

    channel = Column(
        Enum(ConversationChannel),
        default=ConversationChannel.WEB,
        nullable=False,
        index=True,
        comment="Communication channel",
    )

    # ========================================================================
    # CONVERSATION DETAILS
    # ========================================================================

    summary = Column(
        Text,
        nullable=True,
        comment="AI-generated conversation summary",
    )

    intent = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Detected customer intent",
    )

    sentiment = Column(
        String(50),
        nullable=True,
        comment="Overall conversation sentiment",
    )

    # ========================================================================
    # METRICS
    # ========================================================================

    message_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of messages",
    )

    escalation_reason = Column(
        Text,
        nullable=True,
        comment="Reason for escalation (if escalated)",
    )

    priority = Column(
        String(20),
        nullable=True,
        comment="Priority of escalation (if escalated)",
    )

    # [FIX] Add new columns for escalation details
    ticket_id = Column(String, index=True, nullable=True)
    assigned_group = Column(String, nullable=True)

    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================

    customer = relationship(
        "Customer",
        back_populates="conversations",
        lazy="selectin",  # Eager load customer
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",  # Eager load messages
        cascade="all, delete-orphan",  # Delete messages when conversation deleted
        order_by="Message.created_at",  # Order messages by timestamp
    )

    # ========================================================================
    # INDEXES
    # ========================================================================

    __table_args__ = (
        # Index for customer's conversations
        Index("idx_customer_status", "customer_id", "status"),
        # Index for channel + status queries
        Index("idx_channel_status", "channel", "status"),
        # Index for intent-based filtering
        Index("idx_intent", "intent"),
    )

    # ========================================================================
    # PROPERTIES
    # ========================================================================

    @property
    def is_active(self) -> bool:
        """
        Check if conversation is active.

        Returns:
            bool: True if status is ACTIVE
        """
        return self.status == ConversationStatus.ACTIVE

    @property
    def is_resolved(self) -> bool:
        """
        Check if conversation is resolved.

        Returns:
            bool: True if status is RESOLVED
        """
        return self.status == ConversationStatus.RESOLVED

    @property
    def is_escalated(self) -> bool:
        """
        Check if conversation is escalated.

        Returns:
            bool: True if status is ESCALATED
        """
        return self.status == ConversationStatus.ESCALATED

    # ========================================================================
    # METHODS
    # ========================================================================

    def __repr__(self) -> str:
        """String representation of conversation."""
        return (
            f"<Conversation(id={self.id}, "
            f"customer_id={self.customer_id}, "
            f"status='{self.status.value}', "
            f"messages={self.message_count})>"
        )

    def to_dict(self, include_messages: bool = False, include_customer: bool = False) -> dict:
        """
        Convert conversation to dictionary.

        Args:
            include_messages: Whether to include messages
            include_customer: Whether to include customer data

        Returns:
            dict: Conversation data
        """
        data = {
            "id": self.id,
            "customer_id": self.customer_id,
            "title": self.title,
            "status": self.status.value,
            "channel": self.channel.value,
            "summary": self.summary,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "message_count": self.message_count,
            "escalation_reason": self.escalation_reason,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_customer and self.customer:
            data["customer"] = self.customer.to_dict(include_conversations=False)

        if include_messages:
            data["messages"] = [
                msg.to_dict()
                for msg in self.messages
            ]

        return data

    def add_message(self) -> None:
        """
        Increment message count.

        Called when a new message is added to conversation.
        """
        self.message_count += 1

    def mark_resolved(self, summary: str = None) -> None:
        """
        Mark conversation as resolved.

        Args:
            summary: Optional resolution summary
        """
        self.status = ConversationStatus.RESOLVED
        if summary:
            self.summary = summary

    def escalate(self, reason: str, priority: str = None, assigned_group: str = None, ticket_id: str = None) -> None:
        """
        Escalate conversation to human agent.

        Args:
            reason: Reason for escalation
            priority: Priority of escalation (optional)
        """
        self.status = ConversationStatus.ESCALATED
        self.escalation_reason = reason
        if priority:
            self.priority = priority
        self.assigned_group = assigned_group
        self.ticket_id = ticket_id

    def close(self) -> None:
        """Close conversation."""
        self.status = ConversationStatus.CLOSED
