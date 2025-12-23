"""
General Agent Test
"""

import asyncio
from app.agents.general_agent import GeneralAgent

async def test_general_agent():
    """Test general agent."""

    agent = GeneralAgent()

    # Test FAQ queries
    faq_queries = [
        "How do I open an account?",
        "What are your fees?",
        "Is my money safe?",
        "How do I contact support?",
        "What interest rates do you offer?",
    ]

    # Test general queries
    general_queries = [
        "Tell me about your mortgage options",
        "Do you have any special promotions?",
        "How long does transfers take?",
    ]

    print("="*60)
    print("FAQ MATCHING TESTS")
    print("="*60)

    for query in faq_queries:
        print(f"\nQuery: {query}")
        response = await agent.process({"message": query})
        print(f"Source: {response.metadata.get('source')}")
        print(f"Response preview: {response.content[:100]}...")

    print("\n" + "="*60)
    print("GENERAL QUERY TESTS (LLM-based)")
    print("="*60)

    for query in general_queries:
        print(f"\nQuery: {query}")
        response = await agent.process({"message": query})
        print(f"Source: {response.metadata.get('source')}")
        print(f"Response preview: {response.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_general_agent())
