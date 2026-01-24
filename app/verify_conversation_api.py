"""
VERIFY CONVERSATION API (Fixed for Async)
Tests the DB persistence and History API endpoints using AsyncClient.
"""
import asyncio
import sys
from httpx import AsyncClient # pip install httpx
from app.main import app
from app.database import check_db_connection

async def run_api_verification():
    print("\n" + "="*60)
    print("📜 CONVERSATION API TEST (ASYNC)")
    print("="*60)

    # 1. Setup Async Client
    # We use a base_url so we can just use relative paths
    async with AsyncClient(app=app, base_url="http://test") as client:
        print("✅ AsyncClient Initialized")

        # 2. Test Data
        # [CHANGE 3b] Use ID 1 (Guaranteed to exist from seed)
        customer_id = 1
        conversation_id = 500
        message_text = "What is the interest rate for a Personal Loan?"

        # ---------------------------------------------------------
        # STEP 1: Send a Message (Trigger Save to DB)
        # ---------------------------------------------------------
        print(f"\n📤 Sending Message: '{message_text}'...")
        response = await client.post(
            "/api/v1/messages/process",
            json={
                "message": message_text,
                "customer_id": customer_id,
                "conversation_id": conversation_id
            }
        )

        if response.status_code != 200:
            print(f"❌ API Error: {response.text}")
            sys.exit(1)

        data = response.json()
        print("✅ Message Processed.")
        print(f"   🤖 Agent Response: {data['response'][:50]}...")

        real_conversation_id = data["metadata"].get("conversation_id", conversation_id)
        print(f"   ℹ️  Using Real Conversation ID: {real_conversation_id}")

        # ---------------------------------------------------------
        # STEP 2: Fetch History (Test GET /history)
        # ---------------------------------------------------------
        print(f"\n📜 Fetching History for Conversation {real_conversation_id}...")
        hist_response = await client.get(f"/api/v1/conversations/{real_conversation_id}/history")

        if hist_response.status_code != 200:
            print(f"❌ History API Failed: {hist_response.text}")
            sys.exit(1)

        history = hist_response.json()["history"]
        print(f"✅ History Retrieved ({len(history)} items)")

        # Validation
        user_msgs = [m for m in history if m["role"] == "customer"]
        agent_msgs = [m for m in history if m["role"] == "agent"]

        if user_msgs and agent_msgs:
            print(f"   👤 Found User Message: '{user_msgs[0]['content']}'")
            print(f"   🤖 Found Agent Message: '{agent_msgs[0]['content'][:30]}...'")
            print("   ✅ PASS: Both User and Agent messages persisted to DB.")
        else:
            print("   ❌ FAIL: History is missing messages.")

        # ---------------------------------------------------------
        # STEP 3: Fetch Customer Conversations (Test GET /conversations)
        # ---------------------------------------------------------
        print(f"\n🗂️  Fetching Conversations for Customer {customer_id}...")
        conv_response = await client.get(f"/api/v1/customers/{customer_id}/conversations")

        if conv_response.status_code != 200:
            print(f"❌ Conversation List API Failed: {conv_response.text}")
            sys.exit(1)

        convs = conv_response.json()["conversations"]
        target_conv = next((c for c in convs if c["conversation_id"] == real_conversation_id), None)

        if target_conv:
            print(f"✅ Found Conversation {conversation_id} in list.")
            print(f"   📊 Message Count: {target_conv['message_count']}")
            print("   ✅ PASS: Customer Conversation list works.")
        else:
            print(f"   ❌ FAIL: Conversation {conversation_id} not found in customer list.")

if __name__ == "__main__":
    # Ensure DB is up before running
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_db_connection())
    loop.run_until_complete(run_api_verification())
