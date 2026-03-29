import pytest
import logging
from app.agents.account_agent import AccountAgent
from app.agents.base import AgentConfig
from app.services import AccountService, CustomerService, TransactionService
from tests.integration.test_product_agent import assert_hybrid_match

# Silence noise
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

@pytest.fixture
async def account_agent():
    """Enterprise Fixture for Account Agent."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings

    test_engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
    session = AsyncSession(bind=test_engine, expire_on_commit=False)

    try:
        acct_svc = AccountService(db=session)
        cust_svc = CustomerService(db=session)
        txn_svc = TransactionService(db=session)

        config = AgentConfig()
        agent = AccountAgent(
            config=config,
            account_service=acct_svc,
            customer_service=cust_svc,
            transaction_service=txn_svc
        )
        yield agent
    finally:
        await session.close()
        await test_engine.dispose()

@pytest.mark.asyncio
async def test_balance_inquiry(account_agent):
    """Test 1: Ensure AI correctly extracts balance intent and formats response."""
    input_data = {
        "customer_id": "CUST-000001",
        "message": "Hey, I lost my app login. How much cash do I currently possess?"
    }

    response = await account_agent.process(input_data)
    assert response.metadata["query_type"] == "balance"

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["balance", "£", "21,562"], # Should grab the 21562 from the db
        semantic_meaning="The AI provides the user with their current account balance formulated as currency."
    )
    assert is_valid, "AI failed to respond with the formatted balance."


@pytest.mark.asyncio
async def test_unauthorized_user_rejection(account_agent):
    """Test 2: Ensure the agent rejects requests without a customer ID."""
    input_data = {
        "message": "What is my balance?"
    }

    response = await account_agent.process(input_data)
    assert response.confidence == 0.0
    assert "technical difficulties" in response.content.lower()


@pytest.mark.asyncio
async def test_transactions_inquiry(account_agent):
    """Test 3: Ensure AI correctly routes and formats recent transactions."""
    input_data = {
        "customer_id": "CUST-000001",
        "message": "What did I buy recently? Show me my last few purchases."
    }

    response = await account_agent.process(input_data)
    assert response.metadata["query_type"] == "transactions"

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["Argos", "459.87", "recent"], # Argos is the sample data
        semantic_meaning="The AI provides a list of the user's recent transactions or purchases."
    )
    assert is_valid, "AI failed to format the transaction history."


@pytest.mark.asyncio
async def test_statement_inquiry(account_agent):
    """Test 4: Ensure AI handles statement generation requests."""
    input_data = {
        "customer_id": "CUST-000001",
        "message": "I need a PDF of my bank statement for my landlord."
    }

    response = await account_agent.process(input_data)
    assert response.metadata["query_type"] == "statement"

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["statement", "dwilson@example.com", "pdf"],
        semantic_meaning="The AI confirms that a bank statement has been generated and sent to dwilson@example.com."
    )
    assert is_valid, "AI failed to handle the statement request."


@pytest.mark.asyncio
async def test_account_details_inquiry(account_agent):
    """Test 5: Ensure AI provides core account details (status, open date)."""
    input_data = {
        "customer_id": "CUST-000001",
        "message": "What is my actual account number and is the account still active?"
    }

    response = await account_agent.process(input_data)
    assert response.metadata["query_type"] == "details"

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["ACCCUST-00000100", "active", "status"],
        semantic_meaning="The AI provides the user's specific account number and confirms the status of the account."
    )
    assert is_valid, "AI failed to provide account details."


@pytest.mark.asyncio
async def test_general_fallback_inquiry(account_agent):
    """Test 6: Ensure general banking questions fall back gracefully."""
    input_data = {
        "customer_id": "CUST-000001",
        "message": "What are the rules for closing an account?"
    }

    response = await account_agent.process(input_data)
    assert response.metadata["query_type"] == "general"
