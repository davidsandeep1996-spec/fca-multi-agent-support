import asyncio
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.account import Account
from app.models.transaction import Transaction

from app.services.customer import CustomerService
from app.services.account_service import AccountService
from app.services.transaction_service import TransactionService


async def main():
    async with AsyncSessionLocal() as session:
        # --- Raw DB sanity ---
        cust_count = (await session.execute(select(func.count(Customer.id)))).scalar_one()
        acct_count = (await session.execute(select(func.count(Account.id)))).scalar_one()
        txn_count = (await session.execute(select(func.count(Transaction.id)))).scalar_one()
        print("Counts:", {"customers": cust_count, "accounts": acct_count, "transactions": txn_count})

        # pick a real customer id
        customer_id = (await session.execute(select(Customer.id).order_by(Customer.id).limit(1))).scalar_one()
        print("Using customer_id:", customer_id)

        # --- Service sanity ---
        customer_svc = CustomerService(db=session)
        account_svc = AccountService(db=session)
        txn_svc = TransactionService(db=session)

        customer = await customer_svc.get_customer(customer_id)
        print("Customer exists:", bool(customer), "external_customer_id:", getattr(customer, "customer_id", None))

        external_customer_id = getattr(customer, "customer_id", None)
        accounts = await account_svc.get_accounts_by_customer(external_customer_id)
        print("Accounts found:", len(accounts))

        if accounts:
            acct = accounts[0]
            print("First account:", {"id": acct.id, "account_number": acct.account_number, "type": acct.type})

            # NOTE: your TransactionService expects account_id (despite name)
            txns = await txn_svc.get_transactions_by_customer(acct.id, limit=5)
            print("Recent transactions:", len(txns))

if __name__ == "__main__":
    asyncio.run(main())
