from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base import BaseService
from app.repositories.account import AccountRepository
from app.models.account import Account

class AccountService(BaseService):
    def __init__(self, db: AsyncSession = None):
        super().__init__(db)
        if self.db:
            self.repo = AccountRepository(self.db)

    async def __aenter__(self):
        await super().__aenter__()
        self.repo = AccountRepository(self.db)
        return self

    async def get_customer_accounts(self, customer_id: str) -> List[Account]:
        """Get all accounts for a customer ID."""
        return await self.repo.get_by_customer_id(customer_id)

    async def get_account_balance(self, account_number: str) -> Optional[float]:
        """Get balance for a specific account."""
        account = await self.repo.get_by_account_number(account_number)
        return float(account.balance) if account else None

