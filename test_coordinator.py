"""
Agent Coordinator Test
"""

import asyncio
from app.coordinator.agent_coordinator import AgentCoordinator

async def test_coordinator():
    """Test agent coordinator."""

    coordinator = AgentCoordinator()

    print("\n" + "="*60)
    print("AGENT COORDINATOR TEST")
    print("="*60)

    # Simulate multi-turn conversation
    conversations = [
        {
            "conv_id": 1,
            "customer_id": 101,
            "messages": [
                "What's my account balance?",
                "Show me recent transactions",
                "I need a statement",
            ]
        },
        {
            "conv_id": 2,
            "customer_id": 102,
            "messages": [
                "How do I open an account?",
                "What fees do you charge?",
            ]
        },
        {
            "conv_id": 3,
            "customer_id": 103,
            "messages": [
                "I'm not happy with your service!",
                "I want to escalate this issue",
            ]
        },
    ]

    # Process conversations
    for conv_data in conversations:
        conv_id = conv_data["conv_id"]
        customer_id = conv_data["customer_id"]

        print(f"\n--- Conversation {conv_id} (Customer {customer_id}) ---")

        for msg in conv_data["messages"]:
            response = await coordinator.process_message(
                message=msg,
                customer_id=customer_id,
                conversation_id=conv_id,
            )

            print(f"\nMessage: {msg}")
            print(f"Agent: {response['agent']}")
            print(f"Intent: {response['intent']}")
            print(f"Turn: {response['turn_count']}")
            if response.get('escalation_id'):
                print(f"⚠️ Escalated: {response['escalation_id']}")

    # Print statistics
    print("\n" + "="*60)
    print("STATISTICS")
    print("="*60)
    stats = coordinator.get_statistics()
    print(f"Total Conversations: {stats['total_conversations']}")
    print(f"Total Messages: {stats['total_messages']}")
    print(f"Escalated: {stats['escalated_conversations']}")
    print(f"Avg Messages/Conversation: {stats['avg_messages_per_conversation']:.1f}")
    print("\nAgent Distribution:")
    for agent, count in stats['agent_distribution'].items():
        print(f"  {agent}: {count}")
    print("\nIntent Distribution:")
    for intent, count in stats['intent_distribution'].items():
        print(f"  {intent}: {count}")

    # Get conversation history
    print("\n" + "="*60)
    print("CONVERSATION HISTORY (Conv 1)")
    print("="*60)
    history = coordinator.get_conversation_history(1)
    for i, turn in enumerate(history, 1):
        print(f"\nTurn {i}:")
        print(f"  User: {turn['message']}")
        print(f"  Agent: {turn['agent']}")
        print(f"  Intent: {turn['intent']}")

if __name__ == "__main__":
    asyncio.run(test_coordinator())
