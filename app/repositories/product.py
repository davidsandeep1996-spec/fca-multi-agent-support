"""
Product Repository
Data access layer for Product model.
"""
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.repositories.base import BaseRepository

class ProductRepository(BaseRepository[Product]):
    """
    Product repository.
    Handles database operations for financial products.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(Product, db)

    async def get_by_type(self, product_type: str) -> List[Product]:
        """
        Get active products by type (e.g., 'loan', 'savings', 'credit').
        """
        # We filter by type AND ensure the product is active
        result = await self.db.execute(
            select(Product)
            .where(Product.type == product_type)
            .where(Product.is_active == True)
        )
        return result.scalars().all()

    async def get_active_products(self) -> List[Product]:
        """Get all active products."""
        result = await self.db.execute(
            select(Product).where(Product.is_active == True)
        )
        return result.scalars().all()
