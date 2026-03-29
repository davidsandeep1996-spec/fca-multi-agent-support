"""
End-to-End (E2E) Coordinator Tests
 Hits the real Postgres DB and the real Groq LLM API.
Uses actual database records (Customer IDs: 1, 2, 3 | Conv IDs: 1, 2, 3).
"""

import pytest
import logging
from app.coordinator import AgentCoordinator
from app.database import AsyncSessionLocal
from app.services import MessageService

# Silence noisy external logs to keep test output clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)

@pytest.fixture
async def coordinator():
    """Provides the real, stateless Agent Coordinator."""
    return AgentCoordinator()




# ============================================================================
# 1. REAL MULTI-TURN CONVERSATION (Customer 1, Conv 1)
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_multi_turn_account_flow(coordinator):
    """
    Tests memory and context across multiple turns using the real LLM and DB.
    """
    customer_id = 1
    conversation_id = 1

    # Turn 1: Vague intent (Should route to General)
    response_1 = await coordinator.process_message(
        message="Hello, I need some help with my finances.",
        customer_id=customer_id,
        conversation_id=conversation_id
    )
    assert response_1["status"] == "success"
    assert response_1["agent"] in ["general", "system"]

    # Turn 2: Specific Account Request (Should route to Account)
    response_2 = await coordinator.process_message(
        message="Can you tell me my current account balance?",
        customer_id=customer_id,
        conversation_id=conversation_id
    )
    assert response_2["status"] == "success"
    assert response_2["agent"] == "account"
    assert "intent" in response_2

    # Verify DB Persistence
    async with AsyncSessionLocal() as session:
        msg_svc = MessageService(db=session)
        history = await msg_svc.get_conversation_messages(conversation_id)
        assert len(history) >= 4 # At least 2 user messages and 2 agent responses

# ============================================================================
# 2. REAL KNOWLEDGE INQUIRY WITH RAG (Customer 2, Conv 2)
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_knowledge_rag_flow(coordinator):
    """
    Tests Vector DB (pgvector) retrieval and real LLM synthesis.
    """
    customer_id = 2
    conversation_id = 2

    response = await coordinator.process_message(
        message="What is the penalty if I withdraw money early from my Fixed Rate Bond?",
        customer_id=customer_id,
        conversation_id=conversation_id
    )

    assert response["status"] == "success"
    # Should use the General Agent reading the FCA faqs.pdf we uploaded earlier
    assert response["agent"] == "general"
    assert response["intent"] == "knowledge_inquiry"

    # The real LLM should have synthesized the penalty rule from the RAG
    assert "locked" in response["response"].lower() or "term" in response["response"].lower()

# ============================================================================
# 3. REAL HUMAN ESCALATION (Customer 3, Conv 3)
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_human_escalation_flow(coordinator):
    """
    Tests LangGraph Checkpointer pausing the graph for an angry customer.
    """
    customer_id = 98
    conversation_id = 98

    # Send an unhappy message to trigger the Complaint intent
    response = await coordinator.process_message(
        message="I want to file a formal complaint about my account.",
        customer_id=customer_id,
        conversation_id=conversation_id
    )

    # Assert Coordinator caught the paused graph
    assert response["status"] == "paused"
    assert response["escalated"] is True
    assert "escalation_id" in response
    assert "human review" in response["response"].lower()

# ============================================================================
# 4. REAL SSE STREAMING TEST (Customer 10, Conv 14)
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_streaming_events(coordinator):
    """
    Tests that the frontend receives real-time typing indicators.
    """
    customer_id = 10
    conversation_id = 14

    events = []
    # Consume the real async generator
    async for event in coordinator.stream_message(
        message="I want to apply for a mortgage.",
        customer_id=customer_id,
        conversation_id=conversation_id
    ):
        events.append(event)

    # We expect multiple status events followed by 1 final response
    assert len(events) >= 3
    assert events[0]["type"] == "status"
    assert events[0]["step"] == "intent"

    final_event = events[-1]
    assert final_event["type"] == "response"
    assert "mortgage" in final_event["content"].lower()

# ============================================================================
# 5. REAL DASHBOARD ANALYTICS TEST
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_statistics_and_history(coordinator):
    """
    Tests the DB aggregation queries for the Admin Dashboard.
    """
    # 1. Test System Wide Stats
    stats = await coordinator.get_statistics()
    assert "total_conversations" in stats
    assert "total_messages" in stats
    assert stats["total_conversations"] >= 3 # We just ran tests on 3+ convos

    # 2. Test specific Conversation UI History
    history = await coordinator.get_db_conversation_history(conversation_id=1, limit=50)
    assert isinstance(history, list)
    if len(history) > 0:
        assert "role" in history[0]
        assert "content" in history[0]

    # 3. Test Customer specific conversations
    customer_convs = await coordinator.get_db_customer_conversations(customer_id=1)
    assert isinstance(customer_convs, list)
    assert len(customer_convs) >= 1
    assert customer_convs[0]["conversation_id"] == 1




