"""
Message Router API Test
"""

import asyncio
from fastapi.testclient import TestClient
from app.main import app  # Assuming FastAPI app in app/main.py

def test_message_api():
    """Test message API endpoints."""

    client = TestClient(app)

    print("\n" + "="*60)
    print("MESSAGE ROUTER API TEST")
    print("="*60)

    # Test health check
    print("\n1️⃣ Health Check")
    response = client.get("/api/v1/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    # Test message processing
    print("\n2️⃣ Process Message")
    response = client.post(
        "/api/v1/messages/process",
        json={
            "message": "What's my account balance?",
            "customer_id": 101,
            "conversation_id": 1,
        }
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {result['response'][:100]}...")
    print(f"Agent: {result['metadata']['agent']}")
    print(f"Intent: {result['metadata']['intent']}")

    # Test conversation history
    print("\n3️⃣ Get Conversation History")
    response = client.get("/api/v1/conversations/1/history")
    if response.status_code == 200:
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Conversation: {data['conversation_id']}")
        print(f"Messages: {len(data['history'])}")

    # Test statistics
    print("\n4️⃣ Get Statistics")
    response = client.get("/api/v1/statistics")
    if response.status_code == 200:
        print(f"Status: {response.status_code}")
        stats = response.json()
        print(f"Total Conversations: {stats['total_conversations']}")
        print(f"Total Messages: {stats['total_messages']}")
        print(f"Escalations: {stats['escalated_conversations']}")

if __name__ == "__main__":
    test_message_api()
