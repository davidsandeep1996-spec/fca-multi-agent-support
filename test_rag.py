import asyncio
import sys
import os
import logging
import re

# Ensure we can import from the 'app' folder
sys.path.append(os.getcwd())

# Import RAGService directly (Uses Local Embeddings + Local DB = No API Key needed)
from app.services.rag_service import RAGService

# Setup Logging
logging.basicConfig(level=logging.ERROR)

# ==============================================================================
# 🧪 THE ULTIMATE EXAM: 60+ Questions Covering All Pages
# ==============================================================================
TEST_CASES = [
    # --- PAGE 1 ---
    {"page": 1, "q": "What do I do if I lose my debit card?", "expect": ["freeze", "hotline"]},
    {"page": 1, "q": "Can I open a joint account?", "expect": ["yes", "residents"]},
    {"page": 1, "q": "How do I request a new PIN?", "expect": ["biometric", "app"]},
    {"page": 1, "q": "What happens if I enter my PIN incorrectly 3 times?", "expect": ["locked", "atm"]},
    {"page": 1, "q": "Can I use my debit card abroad?", "expect": ["yes", "international"]},
    {"page": 1, "q": "Do I need to tell you before I travel abroad?", "expect": ["no", "notify"]},

    # --- PAGE 2 ---
    {"page": 2, "q": "Can I overpay my Fixed Rate Mortgage?", "expect": ["10%", "ERC"]},
    {"page": 2, "q": "Can I take a payment holiday on my personal loan?", "expect": ["one month", "12 months"]},
    {"page": 2, "q": "How long does a CHAPS payment take?", "expect": ["same working day", "3:30"]},
    {"page": 2, "q": "What is a dormant account?", "expect": ["36 consecutive months", "36 months"]},
    {"page": 2, "q": "What happens if I miss a credit card payment?", "expect": ["12", "fee"]},
    {"page": 2, "q": "Can I install the app on two phones?", "expect": ["one primary", "security"]},

    # --- PAGE 3 ---
    {"page": 3, "q": "What if I am struggling to pay my debts?", "expect": ["financial support", "forbearance"]},
    {"page": 3, "q": "Do you provide documents in Braille?", "expect": ["yes", "large print"]},
    {"page": 3, "q": "How do I change my name on my account?", "expect": ["deed poll", "marriage certificate"]},
    {"page": 3, "q": "How can I get a copy of my bank statement?", "expect": ["7 years", "download"]},
    {"page": 3, "q": "What is a Basic Bank Account?", "expect": ["poor credit", "financial inclusion"]},
    {"page": 3, "q": "How do I upgrade my current account?", "expect": ["income verification", "app"]},

    # --- PAGE 4 ---
    {"page": 4, "q": "How do I order a replacement debit card?", "expect": ["app", "3-5"]},
    {"page": 4, "q": "Can I choose my own PIN?", "expect": ["yes", "atm"]},
    {"page": 4, "q": "What happens to my old account when I use CASS?", "expect": ["close", "automatically"]},
    {"page": 4, "q": "What if someone sends money to my old account after switch?", "expect": ["redirected", "new account"]},
    {"page": 4, "q": "Can I switch if my account is overdrawn?", "expect": ["yes", "agree"]},
    {"page": 4, "q": "Do I need to tell my employer I am switching banks?", "expect": ["no", "automatically"]},

    # --- PAGE 5 ---
    {"page": 5, "q": "Does Section 75 apply to debit cards?", "expect": ["no", "credit cards"]},
    {"page": 5, "q": "What is a Chargeback?", "expect": ["money back", "provider"]},
    {"page": 5, "q": "Why has my account been frozen?", "expect": ["suspicious", "fraud"]},
    {"page": 5, "q": "How do I report a suspicious email?", "expect": ["phishing@fca-bank.com", "forward"]},
    {"page": 5, "q": "Are my cryptocurrency purchases protected?", "expect": ["no", "unregulated"]},
    {"page": 5, "q": "How do I cancel a Direct Debit?", "expect": ["app", "one working day"]},

    # --- PAGE 6 ---
    {"page": 6, "q": "How long does a BACS payment take?", "expect": ["3 working days", "clear"]},
    {"page": 6, "q": "Can I stop a cheque?", "expect": ["yes", "10"]},
    {"page": 6, "q": "Why was my contactless payment declined?", "expect": ["security", "pin"]},
    {"page": 6, "q": "Do you charge for ATM withdrawals?", "expect": ["no", "free"]},
    {"page": 6, "q": "Can I have more than one Cash ISA?", "expect": ["yes", "allowance"]},
    {"page": 6, "q": "How do I transfer an existing ISA to you?", "expect": ["official", "transfer"]},

    # --- PAGE 7 ---
    {"page": 7, "q": "What is a Notice Savings Account?", "expect": ["notice", "withdrawal"]},
    {"page": 7, "q": "Do I have to pay tax on my savings interest?", "expect": ["1,000", "allowance"]},
    {"page": 7, "q": "Can I open a savings account for my child?", "expect": ["junior", "children"]},
    {"page": 7, "q": "What is an Arranged Overdraft?", "expect": ["pre-agreed", "limit"]},
    {"page": 7, "q": "Will applying for an overdraft affect my credit score?", "expect": ["yes", "hard check"]},
    {"page": 7, "q": "Can I withdraw cash using my credit card?", "expect": ["yes", "interest"]},

    # --- PAGE 8 ---
    {"page": 8, "q": "What is a Loan-to-Value (LTV) ratio?", "expect": ["percentage", "property"]},
    {"page": 8, "q": "Can I pay off my personal loan early?", "expect": ["yes", "settle"]},
    {"page": 8, "q": "What is an Early Repayment Charge?", "expect": ["penalty", "mortgage"]},
    {"page": 8, "q": "Can I port my mortgage if I move house?", "expect": ["yes", "portable"]},
    {"page": 8, "q": "What is the difference between Fixed and Tracker mortgage?", "expect": ["guarantees", "fluctuates"]},
    {"page": 8, "q": "Do you offer buy-to-let mortgages?", "expect": ["yes", "25%"]},

    # --- PAGE 9 ---
    {"page": 9, "q": "What should I do if I forget my Mobile App passcode?", "expect": ["reset", "selfie"]},
    {"page": 9, "q": "How do I view my PIN in the app?", "expect": ["card management", "biometric"]},
    {"page": 9, "q": "Can I freeze my card temporarily?", "expect": ["yes", "block"]},
    {"page": 9, "q": "Are biometric logins secure?", "expect": ["yes", "encrypted"]},
    {"page": 9, "q": "How do I turn on push notifications?", "expect": ["settings", "alerts"]},
    {"page": 9, "q": "Does the bank sell my personal data?", "expect": ["no", "gdpr"]},

    # --- PAGE 10 ---
    {"page": 10, "q": "How do I submit a Data Subject Access Request?", "expect": ["online", "dpo"]},
    {"page": 10, "q": "Will you monitor my social media accounts?", "expect": ["no", "fraud"]},
    {"page": 10, "q": "Do you use automated decision making for loans?", "expect": ["yes", "manual review"]},
    {"page": 10, "q": "What happens to an account when someone passes away?", "expect": ["freeze", "death certificate"]},
    {"page": 10, "q": "Who can access the funds of a deceased customer?", "expect": ["executor", "administrator"]},
    {"page": 10, "q": "Do you have a sign language interpreter service?", "expect": ["yes", "signvideo"]},

    # --- PAGE 11 ---
    {"page": 11, "q": "Why would a bank close my account?", "expect": ["free", "discriminate"]},
]

async def run_test():
    print(f"🚀 STARTING EXTENSIVE RAG TEST ({len(TEST_CASES)} Questions)")
    print("   Verifying that the DB finds the correct paragraph for each question.")
    print("=" * 70)

    # Initialize RAG Service directly
    # This uses your LOCAL embedding model (all-MiniLM-L6-v2) and LOCAL Postgres
    rag = RAGService()

    passed = 0
    failed = 0

    for i, test in enumerate(TEST_CASES, 1):
        question = test["q"]
        expected_keywords = test["expect"]
        page = test["page"]

        print(f"📄 [Page {page}] Q{i}: {question}")

        try:
            # 1. Ask the Database (Search only, no generation)
            # We explicitly ask for limit=5 to ensure we search deep enough
            results = await rag.search(question, limit=5)

            if not results:
                print("   ❌ FAIL (No results found)")
                failed += 1
                print("-" * 70)
                continue

            # 2. Extract Text from Results & Normalize
            retrieved_text = ""
            for res in results:
                # Handle both dictionary (from API) and object (from DB) returns
                content = res.get('content') if isinstance(res, dict) else getattr(res, 'content', str(res))
                retrieved_text += " " + str(content)

            # Clean up newlines and spaces for loose matching
            import re
            retrieved_text_clean = re.sub(r'\s+', ' ', retrieved_text).lower()

            # 3. Verify Content
            match_found = False
            for keyword in expected_keywords:
                 # Normalize keyword too
                 keyword_clean = re.sub(r'\s+', ' ', keyword).lower()
                 if keyword_clean in retrieved_text_clean:
                     match_found = True
                     break

            if match_found:
                print(f"   ✅ PASS (Found in DB)")
                passed += 1
            else:
                print(f"   ❌ FAIL")
                print(f"      Retrieved: '{retrieved_text[:150]}...'")
                print(f"      Expected one of: {expected_keywords}")
                failed += 1

        except Exception as e:
            print(f"   ⚠️ ERROR: {e}")
            failed += 1

        print("-" * 70)

    # Final Report
    print("\n" + "=" * 70)
    print(f"📊 FINAL SCORE: {passed}/{len(TEST_CASES)} PASSED")
    print("=" * 70)

    if failed > 0:
        print("💡 TIP: Failures may suggest weak semantic matching for specific phrasing.")
        print("        Consider using a Re-Ranker or Hybrid Search (Keyword + Vector) for 100% accuracy.")

if __name__ == "__main__":
    asyncio.run(run_test())
