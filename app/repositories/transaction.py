from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository

class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: AsyncSession):
        super().__init__(Transaction, db)

    async def get_by_account_id(self, account_id: int, limit: int = 50) -> List[Transaction]:
        """Get recent transactions for an account."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.date.desc())
            .limit(limit)
        )
        return result.scalars().all()
