"""
Integration Tests

End-to-end testing of multi-agent system.
Tests workflow, coordinator, and API together.
"""

import asyncio
import pytest
from app.workflows.message_workflow import MessageWorkflow
from app.coordinator.agent_coordinator import AgentCoordinator


@pytest.fixture
def coordinator():
    """Provide coordinator instance."""
    return AgentCoordinator()


@pytest.fixture
def workflow():
    """Provide workflow instance."""
    return MessageWorkflow()


class TestAccountInquiry:
    """Test account inquiry flows."""

    @pytest.mark.asyncio
    async def test_balance_inquiry(self, coordinator):
        """Test balance inquiry."""
        response = await coordinator.process_message(
            message="What's my account balance?",
            customer_id=101,
            conversation_id=1,
        )

        assert response["agent"] == "account"
        assert response["intent"] == "account_inquiry"
        assert response["confidence"] > 0.8
        assert "balance" in response["response"].lower()

    @pytest.mark.asyncio
    async def test_transaction_history(self, coordinator):
        """Test transaction history request."""
        response = await coordinator.process_message(
            message="Show me my recent transactions",
            customer_id=101,
            conversation_id=1,
        )

        assert response["agent"] == "account"
        assert "transaction" in response["response"].lower()


class TestGeneralInquiry:
    """Test general inquiry flows."""

    @pytest.mark.asyncio
    async def test_faq_match(self, coordinator):
        """Test FAQ matching."""
        response = await coordinator.process_message(
            message="How do I open an account?",
            customer_id=102,
            conversation_id=2,
        )

        assert response["agent"] == "general"
        assert response["intent"] == "general_inquiry"
        assert "account" in response["response"].lower()

    @pytest.mark.asyncio
    async def test_support_info(self, coordinator):
        """Test support information."""
        response = await coordinator.process_message(
            message="How do I contact support?",
            customer_id=102,
            conversation_id=2,
        )

        assert response["agent"] == "general"
        assert "support" in response["response"].lower()


class TestEscalation:
    """Test escalation flows."""

    @pytest.mark.asyncio
    async def test_complaint_escalation(self, coordinator):
        """Test complaint escalation."""
        response = await coordinator.process_message(
            message="I'm not happy with your service!",
            customer_id=103,
            conversation_id=3,
        )

        assert response["agent"] == "human"
        assert response["intent"] == "complaint"
        assert response["escalated"]
        assert response["escalation_id"] is not None

    @pytest.mark.asyncio
    async def test_urgent_escalation(self, coordinator):
        """Test urgent escalation."""
        response = await coordinator.process_message(
            message="My card was stolen! I need immediate help!",
            customer_id=104,
            conversation_id=4,
        )

        assert response["agent"] == "human"
        assert response["escalated"]


class TestMultiTurn:
    """Test multi-turn conversations."""

    @pytest.mark.asyncio
    async def test_conversation_history(self, coordinator):
        """Test multi-turn conversation."""
        conv_id = 5
        customer_id = 105

        # Turn 1
        response1 = await coordinator.process_message(
            message="What's my balance?",
            customer_id=customer_id,
            conversation_id=conv_id,
        )
        assert response1["turn_count"] == 1

        # Turn 2
        response2 = await coordinator.process_message(
            message="Show transactions",
            customer_id=customer_id,
            conversation_id=conv_id,
        )
        assert response2["turn_count"] == 2

        # Turn 3
        response3 = await coordinator.process_message(
            message="I need a statement",
            customer_id=customer_id,
            conversation_id=conv_id,
        )
        assert response3["turn_count"] == 3

        # Verify history
        history = coordinator.get_conversation_history(conv_id)
        assert len(history) == 3


class TestStatistics:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_agent_distribution(self, coordinator):
        """Test agent distribution statistics."""

        # Create messages for different agents
        await coordinator.process_message(
            message="What's my balance?",
            customer_id=101,
            conversation_id=10,
        )

        await coordinator.process_message(
            message="How do I open account?",
            customer_id=102,
            conversation_id=11,
        )

        await coordinator.process_message(
            message="I'm unhappy",
            customer_id=103,
            conversation_id=12,
        )

        # Check statistics
        stats = coordinator.get_statistics()
        assert stats["total_conversations"] > 0
        assert "account" in stats["agent_distribution"]
        assert "general" in stats["agent_distribution"]
        assert "human" in stats["agent_distribution"]

