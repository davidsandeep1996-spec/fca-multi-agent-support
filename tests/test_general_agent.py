import pytest
import logging
from app.agents.general_agent import GeneralAgent
from app.agents.base import AgentConfig
from app.services.faq_service import FAQService
from app.services.rag_service import RAGService
from tests.integration.test_product_agent import assert_hybrid_match

# Silence external logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@pytest.fixture
async def general_agent():
    """True Enterprise Integration Fixture using the REAL Database Services."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings

    # 1. Connect to the real test database
    test_engine = create_async_engine(
        settings.database_url, poolclass=NullPool, echo=False
    )
    session = AsyncSession(bind=test_engine, expire_on_commit=False)

    try:
        # 2. Initialize the REAL services
        faq_svc = FAQService(db=session)
        rag_svc = RAGService()

        config = AgentConfig()
        agent = GeneralAgent(config=config, faq_service=faq_svc, rag_service=rag_svc)
        yield agent
    finally:
        await session.close()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_real_faq_tier1_fast_path(general_agent):
    """Scenario 1: Tests the REAL FAQ Service against seeded database data."""
    # Using exact data from your FAQ seed: "What are your account fees?"
    input_data = {"message": "What are your account fees?"}

    response = await general_agent.process(input_data)

    # 1. Assert it hit the real FAQ database and bypassed the LLM
    assert response.metadata["source"] == "faq_db"
    assert response.confidence == 1.0

    # 2. Assert it pulled the real data ("fee-free banking")
    assert "fee-free banking" in response.content.lower()
    assert "no monthly account fees" in response.content.lower()


@pytest.mark.asyncio
async def test_real_rag_tier2_document_lookup(general_agent):
    """Scenario 2: Tests the REAL Vector RAG Service against the FCA faqs.pdf."""
    # Using exact data from your PDF: "What do I do if I lose my debit card?"
    input_data = {"message": "I lost my debit card, what should I do?"}

    response = await general_agent.process(input_data)

    # 1. Assert it hit the real Vector Database
    assert response.metadata["source"] == "rag_database"

    # 2. Assert the real filename was returned as a citation
    assert "FCA faqs.pdf" in response.metadata["citations"]

    # 3. Use LLM Judge to verify the AI synthesized the real PDF text correctly
    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["freeze", "app", "hotline", "fraud"],
        semantic_meaning="The AI advises the user to freeze their card in the app and contact the 24/7 fraud hotline based on the PDF document.",
    )
    assert is_valid, "AI failed to synthesize the real RAG document correctly."


@pytest.mark.asyncio
async def test_real_rag_accessibility_query(general_agent):
    """Scenario 3: Tests another specific RAG vector search from the PDF."""
    input_data = {
        "message": "Do you offer services for customers with visual impairments?"
    }

    response = await general_agent.process(input_data)

    assert response.metadata["source"] == "rag_database"
    assert "FCA faqs.pdf" in response.metadata["citations"]

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["braille", "audio", "large print", "screen readers"],
        semantic_meaning="The AI confirms support for screen readers and offers Braille, large print, or audio formats.",
    )
    assert is_valid, "AI failed to extract accessibility info from the vector DB."


@pytest.mark.asyncio
async def test_privacy_token_handling(general_agent):
    """Scenario 4: Ensure the LLM strictly adheres to PII masking rules."""
    input_data = {"message": "Hi, my email is [EMAIL] and my name is [NAME]."}
    response = await general_agent.process(input_data)

    # Strict Assertion: The LLM must NOT regurgitate the raw tokens!
    assert "[EMAIL]" not in response.content
    assert "[NAME]" not in response.content

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["details", "information", "safely"],
        semantic_meaning="The AI politely acknowledges receiving the user's information without repeating the specific PII tokens.",
    )
    assert is_valid, "AI violated the PII masking protocol."


@pytest.mark.asyncio
async def test_conversational_memory(general_agent):
    """Scenario 5: Ensure the LLM successfully references conversation history."""
    input_data = {"message": "Wait, what did I just ask you about?"}
    context = {
        "conversation_history": [
            {"role": "user", "content": "I want to apply for a fixed 5-year mortgage."},
            {
                "role": "assistant",
                "content": "I can help you with our mortgage products.",
            },
        ]
    }

    response = await general_agent.process(input_data, context=context)

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["mortgage", "fixed", "5-year"],
        semantic_meaning="The AI accurately recalls that the user was just asking about a fixed 5-year mortgage.",
    )
    assert is_valid, "AI failed to utilize conversation memory."


@pytest.mark.asyncio
async def test_out_of_domain_fallback(general_agent):
    """Scenario 6: Handling general chit-chat safely against a live Vector DB."""
    input_data = {"message": "How do I bake a chocolate cake?"}
    response = await general_agent.process(input_data)

    # ENTERPRISE FIX: In a live DB, RAG always returns the "closest" K documents.
    # The true test is that the LLM reads those banking docs, realizes they
    # don't contain cake recipes, and safely refuses to hallucinate!

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["information", "topic"],
        semantic_meaning="The AI politely explains it does not have the information to answer the question, refusing to hallucinate a cake recipe.",
    )
    assert is_valid, (
        "AI hallucinated cake recipes instead of safely refusing based on the context."
    )
