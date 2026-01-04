"""
Message Workflow Test
"""

import asyncio
from app.workflows.message_workflow import MessageWorkflow

async def test_workflow():
    """Test message workflow."""

    workflow = MessageWorkflow()

    # Print workflow info
    print("\n" + "="*60)
    print("WORKFLOW STRUCTURE")
    print("="*60)
    info = workflow.get_workflow_info()
    for line in info["flow"]:
        print(line)

    # Test scenarios
    test_cases = [
        {
            "message": "i want a credit card?",
            "expected_agent": "account",
        },
        {
            "message": "i want a mortgage?",
            "expected_agent": "general",
        },
        {
            "message": "I'm not happy with your service!",
            "expected_agent": "human",
        },
    ]

    for case in test_cases:
        print("\n" + "="*60)
        print(f"Test: {case['message']}")
        print("="*60)

        response = await workflow.process_message(
            message=case["message"],
            customer_id=1,
            conversation_id=1,
        )

        print(f"Agent: {response.get('agent')}")
        print(f"Intent: {response.get('intent')}")
        print(f"Confidence: {response.get('confidence'):.2f}")
        print(f"\nResponse:\n{response.get('message')[:150]}...")

if __name__ == "__main__":
    asyncio.run(test_workflow())
