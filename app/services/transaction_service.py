from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base import BaseService
from app.repositories.transaction import TransactionRepository
from app.models.transaction import Transaction

class TransactionService(BaseService):
    def __init__(self, db: AsyncSession = None):
        super().__init__(db)
        if self.db:
            self.repo = TransactionRepository(self.db)

    async def __aenter__(self):
        await super().__aenter__()
        self.repo = TransactionRepository(self.db)
        return self

    async def get_recent_transactions(self, account_id: int, limit: int = 10) -> List[Transaction]:
        """Get recent transactions for an account."""
        return await self.repo.get_by_account_id(account_id, limit)
