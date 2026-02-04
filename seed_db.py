import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def seed_customer():
    print("🌱 Seeding Customer ID 1...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Check if customer 1 exists
            result = await session.execute(text("SELECT id FROM customers WHERE id = 1"))
            if result.scalar():
                print("✅ Customer 1 already exists.")
                return

            # 2. Insert Customer 1 (Matching your exact Schema)
            # We explicitly set 'id' to 1 because the test script requests customer_id=1
            # We provide values for all NOT NULL columns found in your schema.
            await session.execute(
                text("""
                INSERT INTO customers (
                    id,
                    first_name,
                    last_name,
                    email,
                    phone,
                    customer_id,
                    is_active,
                    is_verified,
                    is_vip,
                    created_at,
                    updated_at
                )
                VALUES (
                    1,
                    'Test',
                    'User',
                    'test@example.com',
                    '+447700900000',
                    'CUST-001',
                    true,
                    true,
                    false,
                    NOW(),
                    NOW()
                )
                """)
            )
            await session.commit()
            print("✅ Successfully created Customer 1.")
        except Exception as e:
            print(f"❌ Error seeding database: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(seed_customer())
