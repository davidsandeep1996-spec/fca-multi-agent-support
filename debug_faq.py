"""
DEBUG SCRIPT: FAQ Data Layer
Usage: docker compose exec web python -m app.debug_faq
"""
import asyncio
from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from app.models.faq import FAQ
from app.repositories.faq import FAQRepository

async def main():
    print("\n" + "="*50)
    print("🐞 FAQ DATA FORENSICS")
    print("="*50)

    async with AsyncSessionLocal() as session:
        # TEST 1: RAW SQL COUNT
        # Check if the table even has rows
        result = await session.execute(text("SELECT count(*) FROM faqs"))
        count = result.scalar()
        print(f"📊 Total Rows in 'faqs' table: {count}")

        if count == 0:
            print("❌ CRITICAL: Table is empty! You must run the seed script again.")
            return

        # TEST 2: RAW CONTENT DUMP
        # Let's see exactly what is inside the first row
        result = await session.execute(select(FAQ).limit(1))
        first_faq = result.scalar()
        print("\n📝 First FAQ Sample:")
        print(f"   - ID: {first_faq.id}")
        print(f"   - Question: '{first_faq.question}'")
        print(f"   - Keywords: '{first_faq.keywords}'")

        # TEST 3: REPOSITORY SEARCH (Simple Keyword)
        # We search for just "account" to prove the mechanism works
        print("\n🔍 Testing Repository Search (Keyword: 'account')...")
        repo = FAQRepository(session)
        results = await repo.search("account")

        if results:
            print(f"   ✅ FOUND {len(results)} matches!")
            print(f"   - Match 1: {results[0].question}")
        else:
            print("   ❌ SEARCH FAILED for simple keyword.")

        # TEST 4: REPOSITORY SEARCH (Full Sentence)
        # This is what failed in your previous test
        query = "How do I open an account?"
        print(f"\n🔍 Testing Repository Search (Full Sentence: '{query}')...")
        results_full = await repo.search(query)

        if results_full:
             print("   ✅ FOUND match!")
        else:
             print("   ❌ SEARCH FAILED for full sentence.")
             print("   👉 Diagnosis: The search logic (ilike) might be too strict for full sentences.")

if __name__ == "__main__":
    asyncio.run(main())
