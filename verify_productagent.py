# File: app/verify_agent.py
import asyncio
from app.services.product_service import ProductService
from app.agents.product_recommender import ProductRecommenderAgent
from app.database import AsyncSessionLocal

async def main():
    print("\n" + "="*60)
    print("🔍 VERIFYING PRODUCT AGENT (DB CONNECTIVITY)")
    print("="*60)

    async with AsyncSessionLocal() as session:
        # 1. Initialize Service (Connected to DB)
        product_service = ProductService(db=session)

        # 2. Initialize Agent (With Service Injected)
        agent = ProductRecommenderAgent(product_service=product_service)

        # 3. Test Scenarios
        queries = [
            {"intent": "loan_inquiry", "message": "I want a personal loan"},
            {"intent": "savings_inquiry", "message": "Show me savings accounts"},
        ]

        for q in queries:
            print(f"\n🤖 User asks: '{q['message']}'")

            # Run the agent
            response = await agent.process(q)

            # Print results
            print(f"✅ Agent Response Preview: {response.content[:100]}...")

            # Verify data source (Metadata should contain product names from DB)
            found_products = response.metadata.get('products', [])
            print(f"📦 DB Products Found: {found_products}")

            if not found_products:
                print("❌ WARNING: No products found! Check DB seeding.")
            else:
                print("✅ SUCCESS: Data fetched from Database.")

if __name__ == "__main__":
    asyncio.run(main())
