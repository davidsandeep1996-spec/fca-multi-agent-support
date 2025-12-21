import asyncio
from app.agents.intent_classifier import IntentClassifierAgent

async def test_classifier():
    # Create agent
    agent = IntentClassifierAgent()

    # Test messages
    messages = [
        "I want to apply for a mortgage",
        "What is my account balance?",
        "I'm not happy with the service",
        "Hello, can you help me?",
    ]

    for msg in messages:
        print(f"\nMessage: {msg}")

        response = await agent.process({"message": msg})

        print(f"Intent: {response.metadata['intent']}")
        print(f"Confidence: {response.confidence}")
        print(f"Sentiment: {response.metadata['sentiment']}")
        print(f"Routing: {response.metadata['routing']}")
        print(f"Explanation: {response.metadata['explanation']}")

if __name__ == "__main__":
    asyncio.run(test_classifier())
