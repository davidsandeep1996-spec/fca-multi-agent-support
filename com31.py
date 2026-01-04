from app.database import AsyncSessionLocal
from app.repositories import CustomerRepository

# Create session and repository
async def test():
    async with AsyncSessionLocal() as session:
        repo = CustomerRepository(session)

        # Create customer
        data = {
            "customer_id": "CUST-001",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com"
        }
        customer = await repo.create(data)
        await session.commit()

        print(f"Created: {customer}")
        print(f"ID: {customer.id}")

        # Get by email
        found = await repo.get_by_email("john@example.com")
        print(f"Found: {found}")

import asyncio
asyncio.run(test())
