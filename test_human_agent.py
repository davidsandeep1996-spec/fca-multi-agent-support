"""
Human Agent Test
"""

import asyncio
from app.agents.human_agent import HumanAgent

async def test_human_agent():
    """Test human agent."""

    agent = HumanAgent()

    # Test escalation scenarios
    test_cases = [
        {
            "message": "My card was stolen and I need immediate help!",
            "expected_priority": "urgent",
        },
        {
            "message": "I'm not happy with your service. I want to lodge a complaint.",
            "expected_priority": "high",
        },
        {
            "message": "I'd like to speak to someone about changing my account type.",
            "expected_priority": "medium",
        },
        {
            "message": "Can someone help me with my account?",
            "expected_priority": "low",
        },
    ]

    print("="*60)
    print("ESCALATION TESTS")
    print("="*60)

    for case in test_cases:
        print(f"\nMessage: {case['message']}")
        print(f"Expected Priority: {case['expected_priority'].upper()}")

        response = await agent.process({
            "message": case["message"],
            "customer_id": 1,
            "conversation_id": 1,
        })

        actual_priority = response.metadata.get("priority")
        print(f"Actual Priority: {actual_priority.upper()}")
        print(f"Escalation ID: {response.metadata.get('escalation_id')}")
        print(f"Response Preview: {response.content[:80]}...")

if __name__ == "__main__":
    asyncio.run(test_human_agent())
