"""
Base Repository

Provides common CRUD operations for all repositories.
All model-specific repositories should inherit from this.
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BaseModel

# Type variable for models
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Provides:
    - Create: Add new records
    - Read: Query records by ID or filters
    - Update: Modify existing records
    - Delete: Remove records (soft delete supported)
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    # ========================================================================
    # CREATE OPERATIONS
    # ========================================================================

    async def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Create new record.

        Args:
            data: Dictionary with model data

        Returns:
            ModelType: Created instance
        """
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()  # Flush to get ID
        await self.db.refresh(instance)  # Refresh to load relationships
        return instance

    async def create_many(self, data_list: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Create multiple records.

        Args:
            data_list: List of dictionaries with model data

        Returns:
            List[ModelType]: Created instances
        """
        instances = [self.model(**data) for data in data_list]
        self.db.add_all(instances)
        await self.db.flush()

        for instance in instances:
            await self.db.refresh(instance)

        return instances

    # ========================================================================
    # READ OPERATIONS
    # ========================================================================

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get record by ID.

        Args:
            id: Record ID

        Returns:
            ModelType or None: Record if found
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "id"
    ) -> List[ModelType]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            order_by: Column name to order by

        Returns:
            List[ModelType]: List of records
        """
        query = select(self.model).offset(skip).limit(limit)

        # Add ordering
        if hasattr(self.model, order_by):
            query = query.order_by(getattr(self.model, order_by))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_filters(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get records by filters.

        Args:
            filters: Dictionary of column:value filters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List[ModelType]: Filtered records
        """
        query = select(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records.

        Args:
            filters: Optional filters

        Returns:
            int: Number of records
        """
        query = select(func.count(self.model.id))

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        result = await self.db.execute(query)
        return result.scalar()

    async def exists(self, id: int) -> bool:
        """
        Check if record exists.

        Args:
            id: Record ID

        Returns:
            bool: True if exists
        """
        query = select(func.count(self.model.id)).where(self.model.id == id)
        result = await self.db.execute(query)
        return result.scalar() > 0

    # ========================================================================
    # UPDATE OPERATIONS
    # ========================================================================

    async def update(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update record by ID.

        Args:
            id: Record ID
            data: Dictionary with fields to update

        Returns:
            ModelType or None: Updated record
        """
        # Get existing record
        instance = await self.get_by_id(id)
        if not instance:
            return None

        # Update fields
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.db.flush()
        await self.db.refresh(instance)

        return instance

    async def update_many(
        self,
        filters: Dict[str, Any],
        data: Dict[str, Any]
    ) -> int:
        """
        Update multiple records.

        Args:
            filters: Dictionary of filters
            data: Dictionary with fields to update

        Returns:
            int: Number of updated records
        """
        query = update(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        query = query.values(**data)

        result = await self.db.execute(query)
        return result.rowcount

    # ========================================================================
    # DELETE OPERATIONS
    # ========================================================================

    async def delete(self, id: int) -> bool:
        """
        Delete record by ID.

        Args:
            id: Record ID

        Returns:
            bool: True if deleted
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False

        await self.db.delete(instance)
        await self.db.flush()

        return True

    async def delete_many(self, filters: Dict[str, Any]) -> int:
        """
        Delete multiple records.

        Args:
            filters: Dictionary of filters

        Returns:
            int: Number of deleted records
        """
        query = delete(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        result = await self.db.execute(query)
        return result.rowcount
