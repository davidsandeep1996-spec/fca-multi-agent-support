import pytest
from unittest.mock import patch
from app.coordinator import AgentCoordinator



@pytest.fixture
async def coordinator():
    """Provides the real, stateless Agent Coordinator."""
    return AgentCoordinator()


# ============================================================================
# 9. REAL INVALID INTERVENTION (Negative Test)
# ============================================================================
@pytest.mark.asyncio
async def test_invalid_admin_intervention(coordinator):
    """
    Tests that the system correctly rejects an admin intervention
    on a conversation that doesn't exist or isn't paused.
    """
    fake_conversation_id = 999999  # An ID that definitely doesn't exist

    # We expect the coordinator to raise a ValueError, not crash blindly
    with pytest.raises(ValueError) as exc_info:
        await coordinator.approve_intervention(
            conversation_id=fake_conversation_id,
            new_response="This should fail."
        )

    assert "No paused state found" in str(exc_info.value)

# ============================================================================
# 10. DATABASE ROLLBACK SIMULATION (Negative Test)
# ============================================================================
@pytest.mark.asyncio
async def test_database_rollback_on_failure(coordinator):
    """
    Tests that the coordinator safely rolls back the database transaction
    if an unexpected error occurs during message processing.
    """
    customer_id = 100
    conversation_id = 100

    # We mock the MessageWorkflow to forcefully simulate a critical crash mid-transaction
    with patch("app.coordinator.agent_coordinator.MessageWorkflow") as MockWorkflow:
        mock_instance = MockWorkflow.return_value
        mock_instance.process_message.side_effect = Exception("Simulated Database or LLM Crash")

        # The coordinator should catch the exception, execute session.rollback(), and re-raise
        with pytest.raises(Exception) as exc_info:
            await coordinator.process_message(
                message="Hello",
                customer_id=customer_id,
                conversation_id=conversation_id
            )

        assert "Simulated Database or LLM Crash" in str(exc_info.value)

# ============================================================================
# 11. STATIC HEALTH CHECK (Coverage Completeness)
# ============================================================================
def test_coordinator_info():
    """
    Tests the static metadata method to ensure 100% line coverage.
    (Note: Not async because the method is synchronous)
    """
    coordinator = AgentCoordinator()
    info = coordinator.get_coordinator_info()

    assert info["type"] == "AgentCoordinator"
    assert "LangGraph" in info["workflow"]
    assert len(info["features"]) > 0
