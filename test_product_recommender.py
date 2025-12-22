import asyncio
from app.agents.product_recommender import ProductRecommenderAgent

async def test_recommender():
    # Create agent
    agent = ProductRecommenderAgent()

    # Test scenarios
    scenarios = [
        {
            "input": {
                "intent": "loan_inquiry",
                "message": "I'm a first-time buyer looking for a mortgage"
            },
            "context": {
                "customer": {"is_vip": False}
            }
        },
        {
            "input": {
                "intent": "savings_inquiry",
                "message": "I want to save for a house deposit over 3 years"
            },
            "context": {
                "customer": {"is_vip": True}
            }
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*60}")
        print(f"Scenario {i}")
        print(f"{'='*60}")
        print(f"Intent: {scenario['input']['intent']}")
        print(f"Message: {scenario['input']['message']}")
        print(f"VIP: {scenario['context']['customer']['is_vip']}")

        response = await agent.process(
            scenario["input"],
            scenario["context"]
        )

        print(f"\nResponse:\n{response.content}")
        print(f"\nConfidence: {response.confidence}")
        print(f"Products: {[p['name'] for p in response.metadata['products']]}")

if __name__ == "__main__":
    asyncio.run(test_recommender())
