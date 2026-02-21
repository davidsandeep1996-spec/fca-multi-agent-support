import pytest
import asyncio
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.services.rag_service import RAGService

# [CHANGE 3a] Define Golden Test Set
# Questions that MUST pass for the bot to be considered "healthy"
INTEGRATION_TEST_CASES = [
    ("What is the FSCS protection limit?", "85,000"),
    ("What is the CHAPS fee?", "25"),
    ("Do I need to notify you before traveling?", "no"),
    ("Can I overpay my mortgage?", "10%"),
    ("How do I cancel a direct debit?", "app"),
]

@pytest.mark.asyncio
async def test_rag_retrieval_accuracy():
    """
    Integration Test: Verifies the RAG pipeline retrieves correct facts.
    Run with: docker compose exec web pytest tests/test_integration.py
    """
    print("\n🧪 Starting RAG Integration Test...")
    rag = RAGService()

    failures = []

    for question, expected_keyword in INTEGRATION_TEST_CASES:
        # Search DB (Limit 5 to match production settings)
        results = await rag.search(question, limit=5)

        # Combine all retrieved text
        retrieved_text = " ".join([r['content'].lower() for r in results])
        # Check if expected keyword exists
        if expected_keyword.lower() in retrieved_text:
            print(f"✅ PASS: '{question}' -> Found '{expected_keyword}'")
        else:
            print(f"❌ FAIL: '{question}' -> Missing '{expected_keyword}'")
            failures.append(question)

    # Fail the build if any test failed
    assert not failures, f"RAG Check Failed for: {failures}"
