"""
Database Models

This module provides base model classes and common utilities
for all database models in the application.
"""

from datetime import datetime,timezone
from sqlalchemy import Column, Integer, DateTime, Boolean
from typing import Any

from app.database import Base


# ============================================================================
# TIMESTAMP MIXIN
# ============================================================================

class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps to models.

    Automatically sets timestamps on creation and update.
    """

    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
        comment="Record creation timestamp (UTC)",
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
        comment="Record last update timestamp (UTC)",
    )


# ============================================================================
# SOFT DELETE MIXIN
# ============================================================================

class SoftDeleteMixin:
    """
    Mixin to add soft delete functionality to models.

    Instead of deleting records, marks them as deleted with timestamp.
    """

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Record deletion timestamp (NULL if not deleted)",
    )

    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,  # Index for query performance
        comment="Soft delete flag",
    )

    def soft_delete(self) -> None:
        """Mark record as deleted without removing from database."""
        self.is_deleted = True
        self.deleted_at = datetime.now(datetime.timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


# ============================================================================
# BASE MODEL
# ============================================================================

class BaseModel(Base, TimestampMixin):
    """
    Abstract base model with common fields.

    Provides:
    - Auto-incrementing ID
    - Created/updated timestamps
    - String representation
    - Dictionary conversion

    All application models should inherit from this.
    """

    __abstract__ = True  # Don't create table for this class

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key",
    )

    def __repr__(self) -> str:
        """
        String representation of model instance.

        Returns:
            str: Model representation
        """
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self, exclude: set = None) -> dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            exclude: Set of column names to exclude

        Returns:
            dict: Model data as dictionary
        """
        exclude = exclude or set()

        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name not in exclude
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseModel":
        """
        Create model instance from dictionary.

        Args:
            data: Dictionary with model data

        Returns:
            BaseModel: New model instance
        """
        return cls(**data)


# ============================================================================
# EXAMPLE MODEL (for reference)
# ============================================================================

# Example of how to use BaseModel:
#
# from app.models import BaseModel
# from sqlalchemy import Column, String
#
# class Customer(BaseModel):
#     __tablename__ = "customers"
#
#     name = Column(String(100), nullable=False)
#     email = Column(String(255), unique=True, nullable=False)
#     phone = Column(String(20), nullable=True)
#
# This automatically includes:
# - id (primary key)
# - created_at (timestamp)
# - updated_at (timestamp)
# - __repr__() method
# - to_dict() method
# - from_dict() class method


from app.models.customer import Customer
from app.models.conversation import Conversation, ConversationStatus, ConversationChannel
from app.models.message import Message, MessageRole

__all__ = [
    "Base",
    "Customer",
    "Conversation",
    "ConversationStatus",
    "ConversationChannel",
    "Message",
    "MessageRole",
    "TimestampMixin",
    "SoftDeleteMixin",
    "BaseModel",
]
