from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account
from app.repositories.base import BaseRepository

class AccountRepository(BaseRepository[Account]):
    def __init__(self, db: AsyncSession):
        super().__init__(Account, db)

    async def get_by_account_number(self, account_number: str) -> Optional[Account]:
        """Get account by account number."""
        result = await self.db.execute(select(Account).where(Account.account_number == account_number))
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, customer_id: str) -> List[Account]:
        """Get all accounts for a customer."""
        result = await self.db.execute(select(Account).where(Account.customer_id == customer_id))
        return result.scalars().all()
