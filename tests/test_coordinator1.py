"""
End-to-End (E2E) Coordinator Tests
Hits the real Postgres DB and the real Groq LLM API.
"""

import pytest
import logging
from app.coordinator import AgentCoordinator
from app.services import MessageService
from app.services.customer import CustomerService
from app.services.conversation import ConversationService
import random  # Add this to your imports at the top

# Silence noisy external logs to keep test output clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)


@pytest.fixture
async def coordinator():
    """Provides the real, stateless Agent Coordinator."""
    return AgentCoordinator()


# ============================================================================
# ENTERPRISE HELPER FIXTURE
# ============================================================================
@pytest.fixture
async def test_env(db_session):
    """Dynamically creates a fresh customer and conversation for every test."""
    customer_svc = CustomerService(db_session)
    convo_svc = ConversationService(db_session)

    # ENTERPRISE FIX: Generate a random ID to guarantee zero collisions across tests
    unique_id = f"CUST-{random.randint(1000, 99999)}"

    customer = await customer_svc.create_customer(
        customer_id=unique_id,  # <-- The missing argument!
        first_name="Test",
        last_name="User",
        email=f"test.user.{unique_id}@example.com",  # Make the email unique too
    )

    convo = await convo_svc.start_conversation(
        customer_id=customer.id, title="E2E Test Conversation"
    )

    return {"customer_id": customer.id, "conversation_id": convo.id, "db": db_session}


# ============================================================================
# 1. REAL MULTI-TURN CONVERSATION
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_multi_turn_account_flow(coordinator, test_env):
    """Tests memory and context across multiple turns."""
    c_id = test_env["customer_id"]
    conv_id = test_env["conversation_id"]

    # Turn 1: Vague intent
    response_1 = await coordinator.process_message(
        message="Hello, I need some help with my finances.",
        customer_id=c_id,
        conversation_id=conv_id,
    )
    assert response_1["status"] == "success"
    assert response_1["agent"] in ["general", "system"]

    # Turn 2: Specific Account Request
    response_2 = await coordinator.process_message(
        message="Can you tell me my current account balance?",
        customer_id=c_id,
        conversation_id=conv_id,
    )
    assert response_2["status"] == "success"
    assert response_2["agent"] == "account"

    # Verify DB Persistence using the dynamic ID
    msg_svc = MessageService(db=test_env["db"])
    history = await msg_svc.get_conversation_messages(conv_id)
    assert len(history) >= 4


# ============================================================================
# 2. REAL KNOWLEDGE INQUIRY WITH RAG
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
        conversation_id=conversation_id,
    )

    assert response["status"] == "success"
    # Should use the General Agent reading the FCA faqs.pdf we uploaded earlier
    assert response["agent"] == "general"
    assert response["intent"] == "knowledge_inquiry"

    # The real LLM should have synthesized the penalty rule from the RAG
    assert (
        "locked" in response["response"].lower()
        or "term" in response["response"].lower()
    )


# ============================================================================
# 3. REAL HUMAN ESCALATION
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_human_escalation_flow(coordinator, test_env):
    """Tests LangGraph Checkpointer pausing the graph for an angry customer."""

    response = await coordinator.process_message(
        message="I want to file a formal complaint about my account.",
        customer_id=test_env["customer_id"],
        conversation_id=test_env["conversation_id"],
    )

    assert response["status"] == "paused"
    assert response["escalated"] is True
    assert "escalation_id" in response


# ============================================================================
# 4. REAL SSE STREAMING TEST
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_streaming_events(coordinator, test_env):
    """Tests that the frontend receives real-time typing indicators."""

    events = []
    async for event in coordinator.stream_message(
        conversation_id=test_env["conversation_id"],
        message="I want to apply for a mortgage.",
        customer_id=test_env["customer_id"],
    ):
        events.append(event)

    assert len(events) >= 3
    assert events[0]["type"] == "status"
    assert events[-1]["type"] == "response"
    assert "mortgage" in events[-1]["content"].lower()


# ============================================================================
# 5. REAL DASHBOARD ANALYTICS TEST
# ============================================================================
@pytest.mark.asyncio
async def test_e2e_statistics_and_history(coordinator, test_env):
    """Tests the DB aggregation queries using an isolated state."""
    c_id = test_env["customer_id"]
    conv_id = test_env["conversation_id"]

    # 1. Force at least one message into the DB so history is guaranteed to exist
    await coordinator.process_message(
        message="Give me my account history.",
        customer_id=c_id,
        conversation_id=conv_id,
    )

    # 2. Test System Wide Stats
    stats = await coordinator.get_statistics()
    assert "total_conversations" in stats
    assert stats["total_conversations"] >= 1

    # 3. Test specific Conversation UI History
    history = await coordinator.get_db_conversation_history(
        conversation_id=conv_id, limit=50
    )
    assert isinstance(history, list)
    assert len(history) > 0
    assert "role" in history[0]

    # 4. Test Customer specific conversations dynamically!
    customer_convs = await coordinator.get_db_customer_conversations(customer_id=c_id)
    assert len(customer_convs) >= 1
    assert customer_convs[0]["conversation_id"] == conv_id  # Dynamic Assertion!
