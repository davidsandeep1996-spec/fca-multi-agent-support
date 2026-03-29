import pytest
import logging
from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.base import AgentConfig
from app.services import ProductService
from tests.integration.test_product_agent import assert_hybrid_match

# Silence external API logs to keep the test output clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

@pytest.fixture
async def intent_agent():
    """True Enterprise Integration Fixture using REAL Services and REAL LLM."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings

    # 1. Connect to the real test database
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
    session = AsyncSession(bind=test_engine, expire_on_commit=False)

    try:
        # Initialize the real ProductService (in case it's needed downstream)
        prod_svc = ProductService(db=session)
        config = AgentConfig()

        agent = IntentClassifierAgent(config=config, product_service=prod_svc)
        yield agent
    finally:
        await session.close()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_intent_product_acquisition(intent_agent):
    """Scenario 1: User explicitly wants to apply for a specific product."""
    input_data = {"message": "I am looking to buy a house and need to apply for a Fixed Rate Mortgage."}
    response = await intent_agent.process(input_data)

    # 1. Strict Deterministic Routing Asserts
    assert response.metadata["intent"] == "product_acquisition"
    assert response.metadata["routing"] == "product_recommender"
    assert response.confidence > 0.8

    # 2. Hybrid Assert: Verify the LLM's reasoning
    is_valid = await assert_hybrid_match(
        actual_output=response.metadata["explanation"],
        keywords=["apply", "mortgage", "product"],
        semantic_meaning="The reasoning explains that the user is expressing a clear desire to acquire or apply for a mortgage product."
    )
    assert is_valid, "AI failed to justify its product acquisition routing."


@pytest.mark.asyncio
async def test_intent_account_data(intent_agent):
    """Scenario 2: User is asking for specific, numerical personal data."""
    input_data = {"message": "Can you show me my transaction history and current balance?"}
    response = await intent_agent.process(input_data)

    assert response.metadata["intent"] == "account_data"
    assert response.metadata["routing"] == "account_agent"


@pytest.mark.asyncio
async def test_intent_knowledge_inquiry(intent_agent):
    """Scenario 3: The Boundary Test. Mentioning a product, but asking about RULES, not buying."""
    input_data = {"message": "What is the penalty fee if I withdraw early from a Fixed Rate Bond?"}
    response = await intent_agent.process(input_data)

    # This is the ultimate test of the Few-Shot Prompt. It must NOT route to product_acquisition.
    assert response.metadata["intent"] == "knowledge_inquiry"
    assert response.metadata["routing"] == "general_agent"


@pytest.mark.asyncio
async def test_intent_complaint_urgent(intent_agent):
    """Scenario 4: High-stress emergency that requires human intervention."""
    input_data = {"message": "My wallet was stolen and there are fraudulent charges on my credit card!"}
    response = await intent_agent.process(input_data)

    assert response.metadata["intent"] == "complaint"
    assert response.metadata["routing"] == "human_agent"
    assert response.metadata["sentiment"] == "negative"


@pytest.mark.asyncio
async def test_intent_general_inquiry(intent_agent):
    """Scenario 5: Vague pleasantries."""
    input_data = {"message": "Good morning, thank you for your help yesterday."}
    response = await intent_agent.process(input_data)

    assert response.metadata["intent"] == "general_inquiry"
    assert response.metadata["routing"] == "general_agent"
    assert response.metadata["sentiment"] in ["positive", "neutral"]


@pytest.mark.asyncio
async def test_context_aware_routing(intent_agent):
    """Scenario 6: Using memory to override standard routing rules."""
    input_data = {"message": "Wait, what did I just ask you?"}

    # Context injected from a previous turn
    context = {
        "conversation_history": [
            {"role": "user", "content": "I want to apply for a mortgage."},
            {"role": "assistant", "content": "I can help with that application."}
        ]
    }

    response = await intent_agent.process(input_data, context=context)

    # The SPECIAL RULE in the prompt must force this to general_inquiry,
    # even though the history contains "mortgage".
    assert response.metadata["intent"] == "general_inquiry"
    assert response.metadata["routing"] == "general_agent"


@pytest.mark.asyncio
async def test_graceful_error_fallback(intent_agent):
    """Scenario 7: Frontend sends invalid/empty data."""
    input_data = {"message": ""} # Missing required text

    response = await intent_agent.process(input_data)

    # System must catch the ValueError and safely fallback instead of throwing a 500 error
    assert response.confidence == 0.0
    assert response.metadata["intent"] == "general_inquiry"
    assert "error" in response.metadata
