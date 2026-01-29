"""
Verify Evaluation (Full Regression Suite)
HITS THE REAL SERVER AT http://localhost:8000
"""
import asyncio
import time
import importlib.metadata
from httpx import AsyncClient, Timeout
from app.config import settings

# ==============================================================================
# 1. GOLDEN DATASET
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


INTENT_MAPPINGS = {
    "account_inquiry": ["account_inquiry", "account"],
    "product_inquiry": ["product_inquiry", "product", "loan_inquiry", "credit_card", "general_inquiry"],
    "loan_inquiry": ["loan_inquiry", "product", "loan", "product_inquiry"],
    "general_inquiry": ["general_inquiry", "general", "account_inquiry"],
    "complaint": ["complaint", "human_handoff", "human", "general_inquiry"]
}

def print_observability_status():
    print("\n" + "="*80)
    print("🔭 DIAGNOSTICS (Client Side)")
    print("="*80)
    print(f"Target URL:           http://localhost:8000")
    print(f"Langfuse Host:        {settings.langfuse_host}")
    print("="*80 + "\n")

async def run_evaluation():
    print_observability_status()
    print("🧪 STARTING NETWORK TEST (Real Server)")
    print("="*80)

    results = []

    # [FIX] No ASGITransport. Connect to localhost:8000
    async with AsyncClient(base_url="http://localhost:8000", timeout=Timeout(60.0)) as client:

        # 1. First, check if server is actually up
        try:
            resp = await client.get("/api/v1/health")
            if resp.status_code == 200:
                print("✅ Server is UP and reachable!")
            else:
                print(f"❌ Server returned {resp.status_code}. Is it running?")
                return
        except Exception as e:
            print(f"❌ could not connect to server: {e}")
            print("Make sure 'docker compose up' is running in another terminal.")
            return

        # 2. Run Questions
        for i, case in enumerate(GOLDEN_DATA):
            question = case["q"]
            expected_intent = case["intent"]

            # Throttling
            if i > 0 and i % 5 == 0:
                print(f"\n⏳ Pausing 10s...", end="", flush=True)
                time.sleep(10)
                print(" Resuming.")

            print(f"[{i+1}/{len(GOLDEN_DATA)}] Q: '{question}'", end=" ", flush=True)

            result_entry = {"question": question, "status": "fail"}

            try:
                # [FIX] Ensure we send correct payload
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

                    acceptable = INTENT_MAPPINGS.get(expected_intent, [expected_intent])
                    is_match = (actual_intent in acceptable)

                    if is_match:
                        print(f"✅")
                        result_entry["status"] = "pass"
                    else:
                        print(f"⚠️  ({actual_intent})")
                else:
                    print(f"❌ HTTP {response.status_code}")

            except Exception as e:
                print(f"❌ Error: {str(e)[:50]}")

            time.sleep(1)

    print("\n" + "="*80)
    print("DONE. Check your Langfuse Dashboard and /metrics now.")
    print("="*80)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_evaluation())
