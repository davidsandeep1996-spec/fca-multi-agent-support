import pytest
import logging
from app.agents.human_agent import HumanAgent
from app.agents.base import AgentConfig
from app.services import ConversationService

# Silence external API logs to keep test output clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@pytest.fixture
async def human_agent():
    """True Enterprise Integration Fixture using REAL Postgres Database."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings

    # 1. Connect to the real test database
    test_engine = create_async_engine(
        settings.database_url, poolclass=NullPool, echo=False
    )
    session = AsyncSession(bind=test_engine, expire_on_commit=False)

    try:
        # 2. Initialize the REAL service with the live DB session
        conv_svc = ConversationService(db=session)
        config = AgentConfig()

        agent = HumanAgent(config=config, conversation_service=conv_svc)
        yield agent
    finally:
        await session.close()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_urgent_fraud_fast_path(human_agent):
    """Scenario 1: Fast-Path Heuristic catches emergencies instantly."""
    input_data = {
        "message": "My card was stolen and there are unauthorized fraud charges on my account!",
        "customer_id": 9991,
        "conversation_id": 8881,
    }

    response = await human_agent.process(input_data)

    # 1. Verify it was correctly escalated
    assert response.metadata["escalated"] is True
    # 2. Verify the fast-path correctly assigned URGENT priority
    assert response.metadata["priority"] == "urgent"
    # 3. Verify it routed to the right team
    assert response.metadata["assigned_to"] == "Security & Fraud Team"
    # 4. Verify DB insertion attempt occurred (will be True if DB schema is met)
    assert response.metadata["saved"] is True
    # 5. Verify the 15-minute SLA text is generated
    assert "15 minutes" in response.content or "immediately" in response.content.lower()


@pytest.mark.asyncio
async def test_semantic_high_priority_llm(human_agent):
    """Scenario 2: Semantic AI determines this is a severe formal complaint."""
    input_data = {
        "message": "Your system crashed while I was transferring money and now I am missing funds. This is completely unacceptable service and I demand a manager.",
        "customer_id": 9992,
        "conversation_id": 8882,
    }

    response = await human_agent.process(input_data)

    assert response.metadata["escalated"] is True
    # The fast-path won't catch this, the LLM MUST semantically classify it as HIGH
    assert response.metadata["priority"] == "high"
    assert response.metadata["assigned_to"] == "Senior Support Team"
    assert response.metadata["saved"] is True


@pytest.mark.asyncio
async def test_semantic_medium_priority_llm(human_agent):
    """Scenario 3: Semantic AI determines this is a standard support handoff."""
    input_data = {
        "message": "I'm having a little trouble updating my address in the app. Can a human agent help me?",
        "customer_id": 9993,
        "conversation_id": 8883,
    }

    response = await human_agent.process(input_data)

    assert response.metadata["escalated"] is True
    # LLM should classify general help as Medium or Low
    assert response.metadata["priority"] in ["medium", "low"]
    assert response.metadata["saved"] is True


@pytest.mark.asyncio
async def test_missing_input_validation(human_agent):
    """Scenario 4: Graceful degradation when required IDs are missing."""
    input_data = {
        "message": "I want to speak to a human."
        # Missing customer_id and conversation_id!
    }

    response = await human_agent.process(input_data)

    # The system should safely catch the ValueError
    assert response.metadata["escalated"] is False
    assert response.confidence == 0.0
    # Must provide the emergency phone number fallback
    assert "0800-123-4567" in response.content


@pytest.mark.asyncio
async def test_real_db_outage_fallback(human_agent):
    """Scenario 5: Simulates a real Postgres disconnection to prove fault-tolerance."""

    # We deliberately break the active database session connection to simulate a DB crash
    human_agent.conversation_service.db = None

    input_data = {
        "message": "I need to file a formal complaint right now.",
        "customer_id": 9994,
        "conversation_id": 8884,
    }

    # Even though the DB is down, the app MUST NOT crash with a 500 error!
    response = await human_agent.process(input_data)

    # It must fail safely and instruct the user to call
    assert response.metadata["escalated"] is False
    assert response.confidence == 0.0
    assert "0800-123-4567" in response.content
