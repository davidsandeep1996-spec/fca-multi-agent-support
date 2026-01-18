"""
DEBUG: Agent Wiring Check
Usage: docker compose exec web python -m app.debug_wiring
"""
import asyncio
from app.database import AsyncSessionLocal
from app.repositories.faq import FAQRepository
from app.services.faq_service import FAQService
from app.agents.general_agent import GeneralAgent

async def main():
    print("\n" + "="*50)
    print("🔌 AGENT WIRING DIAGNOSTIC")
    print("="*50)

    async with AsyncSessionLocal() as session:
        # --- LINK 1: THE REPOSITORY ---
        print("\n[1] Testing REPOSITORY Layer...")
        repo = FAQRepository(session)
        # We search for "account" because we know it exists
        repo_results = await repo.search("account")
        if repo_results:
            print(f"    ✅ Repository works! Found {len(repo_results)} matches.")
            print(f"       Sample: {repo_results[0].question}")
        else:
            print("    ❌ Repository returned EMPTY list. (Check DB Seed)")
            return

        # --- LINK 2: THE SERVICE ---
        print("\n[2] Testing SERVICE Layer...")
        # We init service with the SAME session
        service = FAQService(db=session)

        # Check if service actually created the repo
        if hasattr(service, 'repo') and service.repo:
            print("    ✅ Service has initialized Repository.")
        else:
            print("    ❌ Service failed to initialize Repository.")
            return

        # Try searching via service
        service_results = await service.search_faqs("account")
        if service_results:
            print(f"    ✅ Service works! Found {len(service_results)} matches.")
        else:
            print("    ❌ Service returned EMPTY list (but Repo worked?).")
            return

        # --- LINK 3: THE AGENT ---
        print("\n[3] Testing AGENT Layer...")
        # Inject the working service into the agent
        agent = GeneralAgent(faq_service=service)

        # Check if agent received the service
        if agent.faq_service:
            print("    ✅ Agent received FAQService.")
        else:
            print("    ❌ Agent.faq_service is None! Injection failed.")
            return

        # Force the specific lookup method (Bypassing process() to test logic)
        print("    👉 Testing internal lookup logic...")
        direct_lookup = await agent._lookup_faq_db("How do I open an account?")
        if direct_lookup:
            print("    ✅ Internal Lookup Success!")
        else:
            print("    ❌ Internal Lookup returned None.")

        # Full Process Test
        print("    👉 Testing full process()...")
        response = await agent.process({"message": "How do I open an account?"})
        print(f"    ✅ Final Output Source: {response.metadata.get('source')}")

if __name__ == "__main__":
    asyncio.run(main())
