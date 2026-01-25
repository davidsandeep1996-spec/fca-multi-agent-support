"""
Verify Evaluation (Full Regression Suite)
Runs 50 Golden Questions with strict throttling (1 min sleep every 3 requests)
to guarantee completion on Free Tier API keys.
"""
import asyncio
import time
import sys
from httpx import AsyncClient, Timeout
from app.main import app
from app.database import check_db_connection

# ==============================================================================
# 1. GOLDEN DATASET (50 Questions)
# ==============================================================================
GOLDEN_DATA = [
    # --- ACCOUNT INQUIRY ---
    {"q": "What is my current account balance?", "intent": "account_inquiry"},
    {"q": "How much money do I have?", "intent": "account_inquiry"},
    {"q": "Show me my recent transactions", "intent": "account_inquiry"},
    {"q": "List my last 5 purchases", "intent": "account_inquiry"},
    {"q": "Did I spend money at Starbucks yesterday?", "intent": "account_inquiry"},
    {"q": "What is my savings account number?", "intent": "account_inquiry"},
    {"q": "Do I have any pending transfers?", "intent": "account_inquiry"},
    {"q": "Check my checking account balance", "intent": "account_inquiry"},
    {"q": "Download my monthly statement", "intent": "account_inquiry"},
    {"q": "When was my last deposit?", "intent": "account_inquiry"},
    {"q": "What is the routing number for my account?", "intent": "account_inquiry"},
    {"q": "Can you show me my transaction history?", "intent": "account_inquiry"},
    {"q": "How much interest have I earned?", "intent": "account_inquiry"},
    {"q": "What's my available credit?", "intent": "account_inquiry"},
    {"q": "Balance check please", "intent": "account_inquiry"},

    # --- PRODUCT INQUIRY ---
    {"q": "I want to apply for a personal loan", "intent": "loan_inquiry"},
    {"q": "What are your mortgage rates?", "intent": "loan_inquiry"},
    {"q": "Tell me about your credit cards", "intent": "product_inquiry"},
    {"q": "Do you offer student loans?", "intent": "loan_inquiry"},
    {"q": "I need a high interest savings account", "intent": "product_inquiry"},
    {"q": "What are the terms for a fixed rate mortgage?", "intent": "loan_inquiry"},
    {"q": "Can I get a loan for a new car?", "intent": "loan_inquiry"},
    {"q": "Compare your credit card options", "intent": "product_inquiry"},
    {"q": "I want to open a new ISA", "intent": "product_inquiry"},
    {"q": "What are the interest rates for savings?", "intent": "product_inquiry"},
    {"q": "How do I apply for a gold credit card?", "intent": "product_inquiry"},
    {"q": "Tell me about the Platinum account", "intent": "product_inquiry"},
    {"q": "I am looking for a travel insurance product", "intent": "product_inquiry"},
    {"q": "What investment products do you have?", "intent": "product_inquiry"},
    {"q": "I want to borrow 5000 pounds", "intent": "loan_inquiry"},

    # --- GENERAL INQUIRY ---
    {"q": "What are your opening hours?", "intent": "general_inquiry"},
    {"q": "Where is the nearest branch?", "intent": "general_inquiry"},
    {"q": "How do I reset my password?", "intent": "general_inquiry"},
    {"q": "Is the app down?", "intent": "general_inquiry"},
    {"q": "What is your phone number?", "intent": "general_inquiry"},
    {"q": "Can I visit a branch on Sunday?", "intent": "general_inquiry"},
    {"q": "How do I change my address?", "intent": "general_inquiry"},
    {"q": "Are you open on bank holidays?", "intent": "general_inquiry"},
    {"q": "What documents do I need to join?", "intent": "general_inquiry"},
    {"q": "Is there parking at the city branch?", "intent": "general_inquiry"},

    # --- COMPLAINT / HUMAN ---
    {"q": "I want to speak to a human", "intent": "complaint"},
    {"q": "This service is terrible, let me talk to a manager", "intent": "complaint"},
    {"q": "I want to make a formal complaint", "intent": "complaint"},
    {"q": "Why was I charged this fee? It's unfair.", "intent": "complaint"},
    {"q": "Escalate this conversation immediately", "intent": "complaint"},
    {"q": "I am very unhappy with your service", "intent": "complaint"},
    {"q": "Connect me to an agent", "intent": "complaint"},
    {"q": "Your bot is not helping me", "intent": "complaint"},
    {"q": "I need to speak to someone about fraud", "intent": "complaint"},
    {"q": "This information is wrong, who can I call?", "intent": "complaint"},
]

# Acceptable mappings (Classifier Intent -> Acceptable Group)
INTENT_MAPPINGS = {
    "account_inquiry": ["account_inquiry", "account"],
    # Allow loan/credit card specific intents to map to 'product' or 'loan'
    "product_inquiry": ["product_inquiry", "product", "loan_inquiry", "credit_card", "general_inquiry"],
    "loan_inquiry": ["loan_inquiry", "product", "loan", "product_inquiry"],
    # Allow account management tasks to fall under general or account
    "general_inquiry": ["general_inquiry", "general", "account_inquiry"],
    "complaint": ["complaint", "human_handoff", "human", "general_inquiry"]
}

async def run_evaluation():
    print("\n" + "="*80)
    print("🧪 FULL REGRESSION TEST (50 Questions)")
    print("   Throttling: 1 minute pause every 3 requests")
    print("="*80)

    results = []

    # Long timeout for the client itself
    async with AsyncClient(app=app, base_url="http://test", timeout=Timeout(60.0)) as client:

        for i, case in enumerate(GOLDEN_DATA):
            question = case["q"]
            expected_intent = case["intent"]

            # --- THROTTLING LOGIC ---
            # Every 3 requests (start index 0: 0, 1, 2 -> pause before 3)
            if i > 0 and i % 3 == 0:
                print(f"\n⏳ [Throttling] Processed {i} requests. Pausing 60s for API quota reset...", end="", flush=True)
                time.sleep(60)
                print(" Resuming.")

            print(f"[{i+1}/{len(GOLDEN_DATA)}] Q: '{question}'", end=" ", flush=True)

            result_entry = {
                "question": question,
                "expected": expected_intent,
                "status": "fail",
                "actual": "N/A",
                "agent": "N/A",
                "error": ""
            }

            try:
                # Use unique ID to prevent context pollution
                response = await client.post(
                    "/api/v1/messages/process",
                    json={
                        "message": question,
                        "customer_id": 1,
                        "conversation_id": 20000 + i
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    actual_intent = data.get("metadata", {}).get("intent", "N/A")
                    agent = data.get("agent", "N/A")

                    # Evaluation Logic
                    acceptable = INTENT_MAPPINGS.get(expected_intent, [expected_intent])
                    is_match = (actual_intent in acceptable)

                    result_entry["actual"] = actual_intent
                    result_entry["agent"] = agent
                    result_entry["status"] = "pass" if is_match else "fail"

                    if is_match:
                        print(f"✅")
                    else:
                        print(f"⚠️  (Got: {actual_intent})")

                else:
                    result_entry["error"] = f"HTTP {response.status_code}"
                    print(f"❌ HTTP {response.status_code}")

            except Exception as e:
                result_entry["error"] = str(e)[:50]
                print(f"❌ {result_entry['error']}")

            results.append(result_entry)

            # Small buffer between normal requests
            time.sleep(1)

    # ==========================================
    # FINAL REPORT
    # ==========================================
    print("\n" + "="*110)
    print("📊 FINAL VERIFICATION REPORT")
    print("="*110)
    print(f"{'QUESTION':<40} | {'EXPECTED':<16} | {'ACTUAL':<16} | {'STATUS'}")
    print("-" * 110)

    passed_count = 0
    for r in results:
        status_icon = "✅" if r["status"] == "pass" else "❌"
        if r["status"] == "pass": passed_count += 1

        q_display = (r['question'][:37] + '..') if len(r['question']) > 37 else r['question']

        # If error exists, show that in Actual column
        actual_display = r['error'] if r['error'] else r['actual']

        print(f"{q_display:<40} | {r['expected']:<16} | {actual_display:<16} | {status_icon}")

    print("="*110)
    print(f"Total: {len(GOLDEN_DATA)} | Passed: {passed_count} | Failed: {len(GOLDEN_DATA) - passed_count}")
    print(f"Accuracy: {(passed_count / len(GOLDEN_DATA)) * 100:.1f}%")
    print("="*110)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_db_connection())
    loop.run_until_complete(run_evaluation())
