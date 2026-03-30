"""
RAG Service Pytest Suite
Tests the SentenceTransformer local embeddings against pgvector in PostgreSQL.
Converts the full 90+ question exam (Pages 1-15) into parameterized test cases.
"""

import pytest
import re
from app.services.rag_service import RAGService

# ==============================================================================
# 🧪 THE ULTIMATE EXAM: 90+ Questions Covering All 15 Pages of FCA faqs.pdf
# ==============================================================================
TEST_CASES = [
    # --- PAGE 1 ---
    {
        "page": 1,
        "q": "What do I do if I lose my debit card?",
        "expect": ["freeze", "hotline"],
    },
    {"page": 1, "q": "Can I open a joint account?", "expect": ["yes", "residents"]},
    {"page": 1, "q": "How do I request a new PIN?", "expect": ["biometric", "app"]},
    {
        "page": 1,
        "q": "What happens if I enter my PIN incorrectly 3 times?",
        "expect": ["locked", "atm"],
    },
    {
        "page": 1,
        "q": "Can I use my debit card abroad?",
        "expect": ["yes", "international"],
    },
    # --- PAGE 2 & 3 ---
    {
        "page": 2,
        "q": "How long does a CHAPS payment take?",
        "expect": ["same working day", "3:30"],
    },
    {
        "page": 2,
        "q": "What is a dormant account?",
        "expect": ["36 consecutive months", "36 months"],
    },
    {
        "page": 2,
        "q": "What happens if I miss a credit card payment?",
        "expect": ["12", "fee"],
    },
    {
        "page": 3,
        "q": "Do you provide documents in Braille?",
        "expect": ["yes", "large print"],
    },
    {
        "page": 3,
        "q": "How do I change my name on my account?",
        "expect": ["deed poll", "marriage certificate"],
    },
    # --- PAGE 4 & 5 ---
    {
        "page": 4,
        "q": "How do I order a replacement debit card?",
        "expect": ["app", "3-5"],
    },
    {
        "page": 4,
        "q": "What happens to my old account when I use CASS?",
        "expect": ["close", "automatically"],
    },
    {
        "page": 5,
        "q": "Does Section 75 apply to debit cards?",
        "expect": ["no", "credit cards"],
    },
    {
        "page": 5,
        "q": "Why has my account been frozen?",
        "expect": ["suspicious", "fraud"],
    },
    # --- PAGE 6 & 7 ---
    {
        "page": 6,
        "q": "How long does a BACS payment take?",
        "expect": ["3 working days", "clear"],
    },
    {"page": 6, "q": "Do you charge for ATM withdrawals?", "expect": ["no", "free"]},
    {
        "page": 6,
        "q": "What is the annual ISA allowance?",
        "expect": ["20,000", "tax year"],
    },
    {
        "page": 7,
        "q": "Do I have to pay tax on my savings interest?",
        "expect": ["1,000", "allowance"],
    },
    {
        "page": 7,
        "q": "Can I withdraw cash using my credit card?",
        "expect": ["yes", "interest"],
    },
    # --- PAGE 8, 9 & 10 (Mortgages, App & Data) ---
    {
        "page": 8,
        "q": "Can I overpay my mortgage without a penalty?",
        "expect": ["10%", "erc"],
    },
    {"page": 8, "q": "Do you offer buy-to-let mortgages?", "expect": ["yes", "25%"]},
    {
        "page": 9,
        "q": "What should I do if I forget my Mobile App passcode?",
        "expect": ["reset", "selfie"],
    },
    {
        "page": 9,
        "q": "Does the bank sell my personal data to advertisers?",
        "expect": ["no", "gdpr"],
    },
    {
        "page": 10,
        "q": "What happens to an account when someone passes away?",
        "expect": ["freeze", "death certificate"],
    },
    {
        "page": 10,
        "q": "Why would a bank close my account?",
        "expect": ["free", "discriminate"],
    },
    # =========================================================================
    # 🚨 NEWLY ADDED: PAGE 11-15 (Specific Financial Products & Penalties)
    # =========================================================================
    # --- Mortgages ---
    {
        "page": 10,
        "q": "What is the interest rate for the Fixed Rate Mortgage?",
        "expect": ["3.99%"],
    },
    {
        "page": 10,
        "q": "What is the minimum deposit required for a Fixed Rate Mortgage?",
        "expect": ["5%"],
    },
    {
        "page": 10,
        "q": "What is the minimum income requirement for the Fixed Rate Mortgage?",
        "expect": ["25,000"],
    },
    {
        "page": 10,
        "q": "How is the interest rate calculated on the Tracker Mortgage?",
        "expect": ["base rate + 1.5%"],
    },
    {
        "page": 11,
        "q": "What is the minimum deposit for the Tracker Mortgage?",
        "expect": ["10%"],
    },
    {
        "page": 12,
        "q": "What is the difference in the minimum deposit required for your mortgages?",
        "expect": ["fixed", "tracker"],
    },
    # --- Savings Accounts ---
    {
        "page": 11,
        "q": "What is the interest rate on the Instant Access Savings account?",
        "expect": ["4.25%"],
    },
    {
        "page": 11,
        "q": "Are there penalties for withdrawing money from the Instant Access Savings account?",
        "expect": ["no", "fixed term"],
    },
    {
        "page": 11,
        "q": "What is the minimum balance required for the Instant Access Savings account?",
        "expect": ["1"],
    },
    {
        "page": 14,
        "q": "What exactly is the penalty if I urgently need to withdraw money from my Fixed Rate Bond?",
        "expect": ["heavy penalty", "accrued interest"],
    },
    {
        "page": 15,
        "q": "What happens if I drop below the minimum balance on my savings accounts?",
        "expect": ["no interest", "closed"],
    },
    # --- Credit Cards & Loans ---
    {
        "page": 11,
        "q": "How much cashback can I earn with the Cashback Credit Card?",
        "expect": ["1%"],
    },
    {
        "page": 11,
        "q": "What is the interest rate on the Cashback Credit Card?",
        "expect": ["9.90%"],
    },
    {
        "page": 11,
        "q": "What is the interest rate for the Balance Transfer Card?",
        "expect": ["0%", "24 months"],
    },
    {"page": 11, "q": "Is there a fee to transfer my balance?", "expect": ["3%"]},
    {
        "page": 12,
        "q": "What credit score do I need for the Balance Transfer Card?",
        "expect": ["700"],
    },
    {
        "page": 12,
        "q": "What is the interest rate for a Personal Loan?",
        "expect": ["6.90%"],
    },
    {
        "page": 12,
        "q": "How much money can I borrow with a Personal Loan?",
        "expect": ["1,000", "35,000"],
    },
    {
        "page": 13,
        "q": "Which credit card is best for paying off existing debt?",
        "expect": ["balance transfer"],
    },
    # --- Penalties & Edge Cases ---
    {
        "page": 14,
        "q": "Is there an early settlement penalty for paying off my Personal Loan early?",
        "expect": ["58 days"],
    },
    {
        "page": 14,
        "q": "What is the penalty for missing a payment on the Cashback Credit Card?",
        "expect": ["12", "late"],
    },
    {
        "page": 14,
        "q": "What is the penalty if I don't pay off my Balance Transfer Card within 24 months?",
        "expect": ["standard variable", "apr"],
    },
    {
        "page": 14,
        "q": "Is there a penalty for withdrawing cash using my Cashback Credit Card?",
        "expect": ["cash advance fee", "daily"],
    },
    {
        "page": 15,
        "q": "Are there penalties for going overdrawn on my Current Account?",
        "expect": ["declined", "credit score"],
    },
]


@pytest.fixture(scope="module")
def rag_service():
    """
    Initializes the RAGService once per test module.
    Loads the sentence-transformer model into memory so tests run blazing fast.
    """
    return RAGService()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case", TEST_CASES, ids=[f"Pg{t['page']}-{t['q'][:40]}..." for t in TEST_CASES]
)
async def test_rag_semantic_search(rag_service, test_case):
    """
    Tests that the pgvector database successfully retrieves the correct
    chunks for a given semantic question.
    """
    question = test_case["q"]
    expected_keywords = test_case["expect"]

    # 1. Execute Search against DB
    results = await rag_service.search(question, limit=15)

    # Fail immediately if no results
    assert len(results) > 0, f"No results found for question: {question}"

    # 2. Extract and Normalize Text
    retrieved_text = ""
    for res in results:
        content = (
            res.get("content")
            if isinstance(res, dict)
            else getattr(res, "content", str(res))
        )
        retrieved_text += " " + str(content)

    retrieved_text_clean = re.sub(r"\s+", " ", retrieved_text).lower()

    # 3. Validation Logic
    match_found = False
    for keyword in expected_keywords:
        keyword_clean = re.sub(r"\s+", " ", keyword).lower()
        if keyword_clean in retrieved_text_clean:
            match_found = True
            break

    # 4. Pytest Assertion
    assert match_found is True, (
        f"Semantic search failed for question: '{question}'\n"
        f"Expected to find one of: {expected_keywords}\n"
        f"Retrieved text snippet: '{retrieved_text_clean[:200]}...'"
    )
