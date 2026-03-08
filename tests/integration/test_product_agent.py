import pytest
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.base import AgentConfig
from app.services import ProductService  # Import your DB service if needed

# ============================================================================
# PYTEST FIXTURES
# ============================================================================


@pytest.fixture
def product_agent():
    """Initializes the agent once for all tests in this suite."""
    # Note: Ensure this matches the exact model you want to test in CI/CD
    config = AgentConfig(name="test_prod", model="openai/gpt-oss-120b")

    # Assuming ProductService handles its own async DB connection internally
    service = ProductService()
    return ProductRecommenderAgent(config=config, product_service=service)


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
    content = response.content.lower()

    # Assert it recommends the fixed rate for stability but suggests an adviser
    assert "fixed rate mortgage" in content
    assert "adviser" in content or "advisor" in content
    # Assert it does NOT say it is definitively the best
    assert "definitively the better choice" not in content


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
    content = response.content.lower()

    # Assert it caught the £10k requirement and explicitly rejected the user
    assert "10,000" in content or "5%" in content
    assert "do not" in content or "not qualify" in content


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
    content = response.content.lower()

    assert "35,000" in content
    assert "exceeds" in content or "not be able" in content


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
    content = response.content.lower()

    # It must recommend Instant Access and warn that the Bond is locked
    assert "instant access savings" in content
    assert "locked" in content or "penalty" in content


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
    content = response.content.lower()

    assert "700" in content
    assert "not eligible" in content or "do not meet" in content


@pytest.mark.asyncio
async def test_age_limit_rejection(product_agent):
    """Test 6: Ensure AI rejects a 14-year-old for a Current Account (req: 16)."""
    message = "My 14-year-old daughter wants to start managing her own allowance. Can she open a Current Account with a debit card?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )
    content = response.content.lower()

    assert "16" in content
    assert "not eligible" in content


@pytest.mark.asyncio
async def test_minimum_balance_rejection(product_agent):
    """Test 7: Ensure AI rejects £400 for Bond (req: £1000)."""
    message = "I want to lock away my spare change. I have £400 right now and want the 5.10% guaranteed interest rate. Can I open the Fixed Rate Bond?"

    response = await product_agent.process(
        {"intent": "product_acquisition", "message": message}
    )
    content = response.content.lower()

    assert "1,000" in content
    assert "not meet" in content or "cannot open" in content


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
    content = response.content.lower()

    # It must state that the payments or interest rate will decrease/fall
    assert "decrease" in content or "fall" in content or "lower" in content
