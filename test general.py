"""
Script to verify General Agent DB Connection.
Usage: docker compose exec web python -m app.verify_general_agent
"""
import asyncio
from app.database import AsyncSessionLocal
from app.services.faq_service import FAQService
from app.agents.general_agent import GeneralAgent

async def main():
    print("\n" + "="*60)
    print("🔍 VERIFYING GENERAL AGENT (FAQ DB LOOKUP)")
    print("="*60)

    async with AsyncSessionLocal() as session:
        # 1. Initialize Service (Connected to Real DB)
        faq_service = FAQService(db=session)

        # 2. Initialize Agent (With Service Injected)
        # Note: We don't pass 'config' here so it defaults to basic settings
        agent = GeneralAgent(faq_service=faq_service)

        # 3. Test Scenarios
        # These questions match keywords in our seeded DB
        queries = [
            "How do I open an account?",   # Matches category: account
            "Is my money safe?",           # Matches category: security
            "What can I do in the app?",   # Matches category: digital
            "Tell me a joke",              # Should fail DB and fallback to LLM
        ]

        for question in queries:
            print(f"\n❓ User asks: '{question}'")

            # Run the agent
            response = await agent.process({"message": question})

            # Analyze Result
            source = response.metadata.get("source", "unknown")
            confidence = response.metadata.get("confidence", 0.0)

            print(f"   👉 Source: {source.upper()}")
            print(f"   👉 Confidence: {confidence}")
            print(f"   👉 Answer Preview: {response.content[:80]}...")

            # Validation Logic
            if source == "faq_db":
                print("   ✅ SUCCESS: Fetched from Database")
            elif source == "llm_fallback":
                print("   ⚠️ NOTE: Fallback to LLM (Expected for non-FAQ queries)")
            else:
                print("   ❌ FAILURE: Unknown source")

if __name__ == "__main__":
    asyncio.run(main())
