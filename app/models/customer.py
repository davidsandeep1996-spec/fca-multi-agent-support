"""
Customer Model

Represents a customer in the FCA financial services support system.
Stores customer information and links to conversations.
"""

from sqlalchemy import Column, String, Boolean, Text, Index
from sqlalchemy.orm import relationship
from typing import List

from app.models import BaseModel


class Customer(BaseModel):
    """
    Customer model.

    Represents a customer who interacts with the support system.
    Includes personal information, contact details, and relationship
    to conversations.
    """

    __tablename__ = "customers"

    # ========================================================================
    # PERSONAL INFORMATION
    # ========================================================================

    first_name = Column(
        String(100),
        nullable=False,
        comment="Customer first name",
    )

    last_name = Column(
        String(100),
        nullable=False,
        comment="Customer last name",
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # Index for fast lookup
        comment="Customer email address (unique)",
    )

    phone = Column(
        String(20),
        nullable=True,
        comment="Customer phone number",
    )

    # ========================================================================
    # ACCOUNT INFORMATION
    # ========================================================================

    customer_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,  # Index for fast lookup
        comment="External customer ID from core banking system",
    )

    account_number = Column(
        String(50),
        nullable=True,
        comment="Primary account number",
    )

    # ========================================================================
    # STATUS FLAGS
    # ========================================================================

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether customer account is active",
    )

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether customer identity is verified",
    )

    is_vip = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="VIP customer flag (premium service)",
    )

    # ========================================================================
    # ADDITIONAL INFORMATION
    # ========================================================================

    notes = Column(
        Text,
        nullable=True,
        comment="Internal notes about customer",
    )

    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================

    conversations = relationship(
        "Conversation",
        back_populates="customer",
        lazy="selectin",  # Eager load conversations
        cascade="all, delete-orphan",  # Delete conversations when customer deleted
    )

    # ========================================================================
    # INDEXES
    # ========================================================================

    __table_args__ = (
        # Composite index for name searches
        Index("idx_customer_name", "first_name", "last_name"),
        # Index for active VIP customers (common query)
        Index("idx_active_vip", "is_active", "is_vip"),
    )

    # ========================================================================
    # PROPERTIES
    # ========================================================================

    @property
    def full_name(self) -> str:
        """
        Get customer's full name.

        Returns:
            str: First name + last name
        """
        return f"{self.first_name} {self.last_name}"

    @property
    def conversation_count(self) -> int:
        """
        Get number of conversations.

        Returns:
            int: Count of conversations
        """
        return len(self.conversations)

    # ========================================================================
    # METHODS
    # ========================================================================

    def __repr__(self) -> str:
        """String representation of customer."""
        return f"<Customer(id={self.id}, name='{self.full_name}', email='{self.email}')>"

    def to_dict(self, include_conversations: bool = False) -> dict:
        """
        Convert customer to dictionary.

        Args:
            include_conversations: Whether to include conversations

        Returns:
            dict: Customer data
        """
        data = {
            "id": self.id,
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "account_number": self.account_number,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "is_vip": self.is_vip,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_conversations:
            data["conversations"] = [
                conv.to_dict(include_messages=False)
                for conv in self.conversations
            ]
            data["conversation_count"] = self.conversation_count

        return data
