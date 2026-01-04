from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base import BaseService
from app.repositories.product import ProductRepository
from app.models.product import Product

class ProductService(BaseService):
    def __init__(self, db: AsyncSession = None):
        super().__init__(db)
        if self.db:
            self.repo = ProductRepository(self.db)

    async def __aenter__(self):
        await super().__aenter__()
        self.repo = ProductRepository(self.db)
        return self

    async def get_all_products(self) -> List[Product]:
        return await self.repo.get_active_products()

    async def get_products_by_category(self, category: str) -> List[Product]:
        return await self.repo.get_by_type(category)
