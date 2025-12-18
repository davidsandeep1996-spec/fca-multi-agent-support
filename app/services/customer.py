"""
Customer Service

Business logic for customer operations.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.customer import CustomerRepository
from app.models.customer import Customer


class CustomerService(BaseService):
    """
    Customer service.

    Handles customer business logic and operations.
    """

    def __init__(self, db: AsyncSession = None):
        """Initialize customer service."""
        super().__init__(db)
        self.repo = None

    async def __aenter__(self):
        """Enter async context."""
        await super().__aenter__()
        self.repo = CustomerRepository(self.db)
        return self

    # ========================================================================
    # CREATE OPERATIONS
    # ========================================================================

    async def create_customer(
        self,
        customer_id: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: str = None,
        account_number: str = None,
        is_vip: bool = False
    ) -> Customer:
        """
        Create new customer.

        Args:
            customer_id: External customer ID
            first_name: First name
            last_name: Last name
            email: Email address
            phone: Phone number (optional)
            account_number: Account number (optional)
            is_vip: VIP status (default False)

        Returns:
            Customer: Created customer

        Raises:
            ValueError: If email already exists
        """
        # Check if email exists
        existing = await self.repo.get_by_email(email)
        if existing:
            raise ValueError(f"Customer with email {email} already exists")

        # Check if customer_id exists
        existing = await self.repo.get_by_customer_id(customer_id)
        if existing:
            raise ValueError(f"Customer with ID {customer_id} already exists")

        # Create customer
        data = {
            "customer_id": customer_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "account_number": account_number,
            "is_vip": is_vip,
            "is_active": True,
            "is_verified": False,
        }

        customer = await self.repo.create(data)
        await self.commit()

        return customer

    # ========================================================================
    # READ OPERATIONS
    # ========================================================================

    async def get_customer(self, customer_id: int) -> Optional[Customer]:
        """
        Get customer by ID.

        Args:
            customer_id: Customer ID

        Returns:
            Customer or None: Customer if found
        """
        return await self.repo.get_by_id(customer_id)

    async def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """
        Get customer by email.

        Args:
            email: Email address

        Returns:
            Customer or None: Customer if found
        """
        return await self.repo.get_by_email(email)

    async def get_active_customers(
        self,
        page: int = 1,
        page_size: int = 100
    ) -> List[Customer]:
        """
        Get active customers with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[Customer]: Active customers
        """
        skip = (page - 1) * page_size
        return await self.repo.get_active_customers(skip=skip, limit=page_size)

    async def search_customers(
        self,
        name: str,
        page: int = 1,
        page_size: int = 100
    ) -> List[Customer]:
        """
        Search customers by name.

        Args:
            name: Name to search for
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[Customer]: Matching customers
        """
        skip = (page - 1) * page_size
        return await self.repo.search_by_name(name, skip=skip, limit=page_size)

    # ========================================================================
    # UPDATE OPERATIONS
    # ========================================================================

    async def update_customer(
        self,
        customer_id: int,
        data: Dict[str, Any]
    ) -> Optional[Customer]:
        """
        Update customer.

        Args:
            customer_id: Customer ID
            data: Fields to update

        Returns:
            Customer or None: Updated customer
        """
        customer = await self.repo.update(customer_id, data)
        if customer:
            await self.commit()
        return customer

    async def verify_customer(self, customer_id: int) -> Optional[Customer]:
        """
        Verify customer identity.

        Args:
            customer_id: Customer ID

        Returns:
            Customer or None: Verified customer
        """
        return await self.update_customer(customer_id, {"is_verified": True})

    async def make_vip(self, customer_id: int) -> Optional[Customer]:
        """
        Upgrade customer to VIP.

        Args:
            customer_id: Customer ID

        Returns:
            Customer or None: VIP customer
        """
        return await self.update_customer(customer_id, {"is_vip": True})

    async def deactivate_customer(self, customer_id: int) -> Optional[Customer]:
        """
        Deactivate customer account.

        Args:
            customer_id: Customer ID

        Returns:
            Customer or None: Deactivated customer
        """
        return await self.update_customer(customer_id, {"is_active": False})

    # ========================================================================
    # DELETE OPERATIONS
    # ========================================================================

    async def delete_customer(self, customer_id: int) -> bool:
        """
        Delete customer (and all conversations/messages via CASCADE).

        Args:
            customer_id: Customer ID

        Returns:
            bool: True if deleted
        """
        success = await self.repo.delete(customer_id)
        if success:
            await self.commit()
        return success
