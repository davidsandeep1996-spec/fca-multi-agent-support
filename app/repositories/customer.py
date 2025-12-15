"""
Customer Repository

Data access layer for Customer model.
Provides customer-specific query methods.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """
    Customer repository.

    Provides customer-specific data access methods.
    """

    def __init__(self, db: AsyncSession):
        """Initialize customer repository."""
        super().__init__(Customer, db)

    async def get_by_email(self, email: str) -> Optional[Customer]:
        """
        Get customer by email.

        Args:
            email: Customer email

        Returns:
            Customer or None: Customer if found
        """
        result = await self.db.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, customer_id: str) -> Optional[Customer]:
        """
        Get customer by external customer ID.

        Args:
            customer_id: External customer ID

        Returns:
            Customer or None: Customer if found
        """
        result = await self.db.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_active_customers(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Customer]:
        """
        Get active customers.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Customer]: Active customers
        """
        result = await self.db.execute(
            select(Customer)
            .where(Customer.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Customer.created_at.desc())
        )
        return result.scalars().all()

    async def get_vip_customers(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Customer]:
        """
        Get VIP customers.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Customer]: VIP customers
        """
        result = await self.db.execute(
            select(Customer)
            .where(Customer.is_vip == True)
            .where(Customer.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Customer.created_at.desc())
        )
        return result.scalars().all()

    async def search_by_name(
        self,
        name: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Customer]:
        """
        Search customers by name (first or last).

        Args:
            name: Name to search for
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List[Customer]: Matching customers
        """
        search_term = f"%{name}%"

        result = await self.db.execute(
            select(Customer)
            .where(
                (Customer.first_name.ilike(search_term)) |
                (Customer.last_name.ilike(search_term))
            )
            .offset(skip)
            .limit(limit)
            .order_by(Customer.last_name, Customer.first_name)
        )
        return result.scalars().all()
