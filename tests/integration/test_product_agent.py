import pytest
import logging
from groq import AsyncGroq

from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.base import AgentConfig
from app.services import ProductService

from pydantic import BaseModel, Field
from typing import Literal
from app.config import settings

# Silence external libraries that cause terminal noise
logger = logging.getLogger(__name__)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langfuse").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ============================================================================
# LLM JUDGE SCHEMA
# ============================================================================


class EvaluationVerdict(BaseModel):
    """Strict schema for the LLM Judge output."""

    reasoning: str = Field(
        description="A 1-sentence explanation of why the text passes or fails the semantic check."
    )
    verdict: Literal["PASS", "FAIL"] = Field(description="The final strict judgment.")


# ============================================================================
# CASCADING EVALUATION (HYBRID ASSERTER)
# ============================================================================


async def assert_hybrid_match(
    actual_output: str, keywords: list[str], semantic_meaning: str
) -> bool:
    content_lower = actual_output.lower()

    # ⚡ FAST PATH (Keywords)
    if any(keyword.lower() in content_lower for keyword in keywords):
        return True

    # 🧠 FALLBACK PATH (LLM Judge)
    print("\n[⚠️ Keywords not found. Triggering Groq LLM Judge...]")

    client = AsyncGroq(api_key=settings.groq_api_key)

    # 1. SIMPLE PROMPT (No Pydantic Schema here!)
    prompt = f"""
    You are an expert QA Evaluator.
    Evaluate the following text and determine if it conveys this specific meaning: "{semantic_meaning}"

    Text to evaluate: "{actual_output}"

    You must respond with a single valid JSON object. Do NOT wrap it in a list or array.
    It must contain exactly two keys: "reasoning" and "verdict".

    Example Output:
    {{
        "reasoning": "Your 1-sentence explanation of why it passes or fails.",
        "verdict": "PASS"
    }}

    The verdict must be exactly "PASS" or "FAIL".
    """

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw_json = response.choices[0].message.content

        # 2. STRICT PYDANTIC VALIDATION (This is where Pydantic works its magic!)
        judgment = EvaluationVerdict.model_validate_json(raw_json)

        if judgment.verdict == "FAIL":
            print(f"\n[❌ Judge Verdict: FAIL] Reason: {judgment.reasoning}")

        return judgment.verdict == "PASS"

    except Exception as e:
        print(f"\n[🚨 Pydantic Parsing Error]: LLM failed to output valid schema. {e}")
        return False


# ============================================================================
# PYTEST FIXTURES
# ============================================================================


@pytest.fixture
async def product_agent():
    """
    Bulletproof Fixture: Bypasses environment variables entirely and
    forces an isolated NullPool engine strictly for this single test.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings

    # 1. Create a dedicated TEST engine that CANNOT pool connections
    test_engine = create_async_engine(
        settings.database_url, poolclass=NullPool, echo=False
    )

    # 2. Bind the session to this specific isolated engine
    session = AsyncSession(bind=test_engine, expire_on_commit=False)

    try:
        service = ProductService(db=session)
        config = AgentConfig()
        agent = ProductRecommenderAgent(config=config, product_service=service)
        yield agent
    finally:
        # 3. Aggressively clean up both the session AND the engine
        await session.close()
        await test_engine.dispose()


# ============================================================================
# COMPLIANCE & NON-ADVICE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_financial_advice_trap(product_agent):
    """Test 1: Ensure the AI does not give definitive financial advice."""
    message = "I am buying my first house but I'm terrified of interest rates going up next year. Should I get the Fixed Rate Mortgage or the Tracker Mortgage? Tell me which one is definitively the better choice for me."

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    # Assert negative constraint remains strict
    assert "definitively the better choice" not in response.content.lower()

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["adviser", "advisor"],
        semantic_meaning="The AI recommends a fixed rate mortgage but firmly advises the user to consult an independent financial adviser or advisor instead of giving definitive financial advice.",
    )
    assert is_valid, "Failed to appropriately defer to a financial adviser."


# ============================================================================
# MULTI-VARIABLE & MATH ELIGIBILITY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_mortgage_deposit_math_rejection(product_agent):
    """Test 2: Ensure AI calculates 5% of £200k (£10k) and rejects £5k deposit."""
    message = "I earn £40,000 a year and I want to buy a house that costs £200,000. I have managed to save £5,000 for the deposit. Do I qualify for the Fixed Rate Mortgage?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["not qualify", "insufficient", "do not"],
        semantic_meaning="The AI correctly calculates 5% of £200,000 as £10,000, and rejects the user because their £5,000 deposit is insufficient.",
    )
    assert is_valid, "Failed to accurately enforce deposit math."


# ============================================================================
# BOUNDARY ENFORCEMENT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_loan_maximum_boundary(product_agent):
    """Test 3: Ensure AI rejects a loan request exceeding the £35k limit."""
    message = "I am doing a massive home renovation and need to borrow £50,000 to pay the builders. I earn £80,000 a year, so income isn't a problem. Can I use your Personal Loan for this?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["exceeds", "not be able", "not cover", "another product"],
        semantic_meaning="The AI rejects the user's request for a £50,000 loan because the maximum limit for a personal loan is £35,000.",
    )
    assert is_valid, "Failed to enforce the maximum loan boundary."


# ============================================================================
# COMPARATIVE REASONING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_dealbreaker_feature_savings(product_agent):
    """Test 4: Ensure AI picks Instant Access over Bond due to emergency withdrawal needs."""
    message = "I have £10,000 to save and I want the highest interest rate possible. However, there is a chance my car might break down next month and I would need to withdraw £2,000 urgently to fix it. Where should I put the money?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["instant access savings"],
        semantic_meaning="The AI recommends the Instant Access Savings account over the Bond because the user needs to make emergency withdrawals, warning that the Bond locks the funds.",
    )
    assert is_valid, "Failed to prioritize the emergency withdrawal requirement."


# ============================================================================
# EXACT JSON REQUIREMENT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_credit_score_rejection(product_agent):
    """Test 5: Ensure AI rejects user based on the 700 credit score requirement."""
    message = "I am drowning in debt and want to consolidate it. I earn £50,000 a year, but my credit score just dropped to 620 because of missed payments. Can I get the Balance Transfer Card?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["not eligible", "do not meet", "requirements"],
        semantic_meaning="The AI rejects the user for a Balance Transfer Card because their credit score of 620 is below the required 700.",
    )
    assert is_valid, "Failed to enforce credit score minimum."


@pytest.mark.asyncio
async def test_age_limit_rejection(product_agent):
    """Test 6: Ensure AI rejects a 14-year-old for a Current Account (req: 16)."""
    message = "My 14-year-old daughter wants to start managing her own allowance. Can she open a Current Account with a debit card?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["not eligible", "cannot open", "not old enough"],
        semantic_meaning="The AI rejects the 14-year-old from opening a Current Account because the minimum age requirement is 16.",
    )
    assert is_valid, "Failed to enforce minimum age requirements."


@pytest.mark.asyncio
async def test_minimum_balance_rejection(product_agent):
    """Test 7: Ensure AI rejects £400 for Bond (req: £1000)."""
    message = "I want to lock away my spare change. I have £400 right now and want the 5.10% guaranteed interest rate. Can I open the Fixed Rate Bond?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["not meet", "cannot open", "not eligible"],
        semantic_meaning="The AI rejects the £400 deposit for the Fixed Rate Bond because it requires a minimum balance of £1,000.",
    )
    assert is_valid, "Failed to enforce minimum balance constraints."


# ============================================================================
# ECONOMIC LOGIC TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_tracker_mortgage_economic_logic(product_agent):
    """Test 8: Ensure AI understands that base rate drops lower the tracker payments."""
    message = "I am looking at the Tracker Mortgage. What exactly happens to my monthly payments if the Bank of England decides to lower the base rate next month?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )

    is_valid = await assert_hybrid_match(
        actual_output=response.content,
        keywords=["decrease", "fall", "lower"],
        semantic_meaning="The AI correctly explains that if the Bank of England lowers the base rate, the monthly payments or interest rate on a Tracker Mortgage will decrease.",
    )
    assert is_valid, "Failed to reason correctly about tracker mortgage mechanics."
