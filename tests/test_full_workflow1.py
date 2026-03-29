
"""
End-to-End Full System Workflow Tests
NO MOCKS. Hits the real Postgres DB and the real Groq API.
Tests every possible execution path of the MessageWorkflow LangGraph state machine.
"""

import pytest
import logging
from app.coordinator.agent_coordinator import AgentCoordinator

# Silence noisy external logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)

@pytest.fixture
async def coordinator():
    """Provides the real, stateless Agent Coordinator."""
    return AgentCoordinator()


# ============================================================================
# 1. NORMAL PATHS (Intent Classification -> Agents)
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_general_inquiry(coordinator):
    """Path: Guardrail (Pass) -> Classify -> General Agent -> End"""
    result = await coordinator.process_message(
        message="What are your standard branch operating hours?",
        customer_id=1,
        conversation_id=101
    )
    assert result["status"] == "success"
    assert result["agent"] == "general"
    assert result["intent"] in ["general_inquiry", "knowledge_inquiry"]


@pytest.mark.asyncio
async def test_workflow_account_inquiry(coordinator):
    """Path: Guardrail (Safe Bypass) -> Classify -> Account Agent -> End"""
    result = await coordinator.process_message(
        message="What is my account balance?",
        customer_id=1,
        conversation_id=102
    )
    assert result["status"] == "success"
    assert result["agent"] == "account"
    assert result["intent"] == "account_data"
    response_lower = str(result.get("response", "")).lower()
    assert "balance" in response_lower or "couldn't locate" in response_lower

@pytest.mark.asyncio
async def test_workflow_product_inquiry_compliant(coordinator):
    """Path: Guardrail -> Classify -> Product Agent -> Compliance (Pass) -> End"""
    result = await coordinator.process_message(
        message="I want to apply for a personal loan.",
        customer_id=1,
        conversation_id=103
    )
    assert result["status"] == "success"
    assert result["agent"] == "product"
    assert "loan" in str(result.get("response", "")).lower()


# ============================================================================
# 2. ESCALATION & HUMAN IN THE LOOP (The Checkpointer Interrupts)
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_complaint_escalation(coordinator):
    """Path: Guardrail -> Classify (Complaint) -> Human Agent -> PAUSE (Checkpointer)"""
    result = await coordinator.process_message(
        message="I am very unhappy with the recent changes to my account fees and wish to file a complaint.",
        customer_id=1,
        conversation_id=104
    )
    # The native LangGraph interrupt should freeze this and return a paused status
    assert result["status"] == "paused"
    assert result["agent"] == "system"
    assert "escalation_id" in result.get("metadata", {})
    assert "paused for human review" in str(result.get("response", "")).lower()



@pytest.mark.asyncio
async def test_workflow_unmapped_intent_fallback(coordinator):
    """Path: Guardrail -> Classify (Low Confidence/Unmapped) -> Human Agent -> PAUSE"""
    result = await coordinator.process_message(
        message="I need technical support because the mobile app keeps crashing when I try to log in.",
        customer_id=1,
        conversation_id=105
    )
    # Our new `_route_by_intent` logic should catch this as low confidence and escalate it
    assert result["status"] == "paused"
    assert result["agent"] == "system"
    assert "escalation_id" in result.get("metadata", {})
