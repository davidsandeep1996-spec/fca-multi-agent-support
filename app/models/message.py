"""
Message Model

Represents a single message in a conversation between customer and AI system.
Tracks message content, sender, and metadata.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, Boolean, Index
from sqlalchemy.orm import relationship
import enum

from app.models import BaseModel


# ============================================================================
# ENUMS
# ============================================================================

class MessageRole(str, enum.Enum):
    """Message sender role enumeration."""

    CUSTOMER = "customer"      # Message from customer
    AGENT = "agent"            # Message from AI agent
    SYSTEM = "system"          # System message
    HUMAN_AGENT = "human_agent"  # Message from human agent


# ============================================================================
# MESSAGE MODEL
# ============================================================================

class Message(BaseModel):
    """
    Message model.

    Represents a single message in a conversation.
    Contains message content, role, and metadata.
    """

    __tablename__ = "messages"

    # ========================================================================
    # FOREIGN KEYS
    # ========================================================================

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to conversation",
    )

    # ========================================================================
    # MESSAGE CONTENT
    # ========================================================================

    role = Column(
        Enum(MessageRole),
        nullable=False,
        index=True,
        comment="Message sender role",
    )

    content = Column(
        Text,
        nullable=False,
        comment="Message content/text",
    )

    # ========================================================================
    # METADATA
    # ========================================================================

    agent_name = Column(
        String(100),
        nullable=True,
        comment="Name of AI agent that generated message (if role=agent)",
    )

    intent = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Detected intent in customer message",
    )

    sentiment = Column(
        String(50),
        nullable=True,
        comment="Message sentiment (positive, negative, neutral)",
    )

    confidence_score = Column(
        Integer,
        nullable=True,
        comment="Confidence score (0-100) for intent detection",
    )

    # ========================================================================
    # FLAGS
    # ========================================================================

    is_error = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether message represents an error",
    )

    requires_human = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether message requires human agent intervention",
    )

    # ========================================================================
    # ADDITIONAL DATA
    # ========================================================================

    metadata_json = Column(
        Text,
        nullable=True,
        comment="Additional metadata as JSON string",
    )

    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================

    conversation = relationship(
        "Conversation",
        back_populates="messages",
        lazy="selectin",  # Eager load conversation
    )

    # ========================================================================
    # INDEXES
    # ========================================================================

    __table_args__ = (
        # Index for conversation's messages (most common query)
        Index("idx_conversation_created", "conversation_id", "created_at"),
        # Index for role-based filtering
        Index("idx_role", "role"),
        # Index for messages requiring human intervention
        Index("idx_requires_human", "requires_human"),
        # Index for intent-based analytics
        Index("idx_conversation_intent", "conversation_id", "intent"),
    )

    # ========================================================================
    # PROPERTIES
    # ========================================================================

    @property
    def is_customer_message(self) -> bool:
        """
        Check if message is from customer.

        Returns:
            bool: True if role is CUSTOMER
        """
        return self.role == MessageRole.CUSTOMER

    @property
    def is_agent_message(self) -> bool:
        """
        Check if message is from AI agent.

        Returns:
            bool: True if role is AGENT
        """
        return self.role == MessageRole.AGENT

    @property
    def is_system_message(self) -> bool:
        """
        Check if message is system message.

        Returns:
            bool: True if role is SYSTEM
        """
        return self.role == MessageRole.SYSTEM

    @property
    def content_length(self) -> int:
        """
        Get message content length.

        Returns:
            int: Character count
        """
        return len(self.content) if self.content else 0

    # ========================================================================
    # METHODS
    # ========================================================================

    def __repr__(self) -> str:
        """String representation of message."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"<Message(id={self.id}, "
            f"conversation_id={self.conversation_id}, "
            f"role='{self.role.value}', "
            f"content='{content_preview}')>"
        )

    def to_dict(self, include_conversation: bool = False) -> dict:
        """
        Convert message to dictionary.

        Args:
            include_conversation: Whether to include conversation data

        Returns:
            dict: Message data
        """
        data = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value,
            "content": self.content,
            "agent_name": self.agent_name,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "confidence_score": self.confidence_score,
            "is_error": self.is_error,
            "requires_human": self.requires_human,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_conversation and self.conversation:
            data["conversation"] = self.conversation.to_dict(
                include_messages=False,
                include_customer=False
            )

        return data
