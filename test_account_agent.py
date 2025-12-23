import asyncio
from app.agents.account_agent import AccountAgent

async def test_account_agent():
    agent = AccountAgent()

    test_messages = [
        "What's my account balance?",
        "Show me my recent transactions",
        "I need a statement",
        "Tell me about my account",
    ]

    for message in test_messages:
        print("\n" + "="*60)
        print(f"Query: {message}")
        print("="*60)

        response = await agent.process(
            {
                "customer_id": 1,
                "message": message,
            },
            context=None,  # no services needed
        )

        print(f"Response: {response.content}")
        print(f"Query Type: {response.metadata.get('query_type')}")

if __name__ == "__main__":
    asyncio.run(test_account_agent())
