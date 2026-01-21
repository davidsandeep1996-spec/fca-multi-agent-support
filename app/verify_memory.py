"""
VERIFY MEMORY & CONTEXT
Tests if the agent remembers previous turns (Sliding Window Memory).
"""
import asyncio
import logging
import sys
from app.coordinator.agent_coordinator import AgentCoordinator
from app.database import check_db_connection

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

async def main():
    print("\n" + "="*60)
    print("🧠 MEMORY & CONTEXT TEST")
    print("="*60)

    # 1. Check DB
    if not await check_db_connection():
        print("❌ DB Connection Failed!")
        sys.exit(1)

    coordinator = AgentCoordinator()

    # We use a unique conversation ID to ensure clean history
    customer_id = 1
    conversation_id = 999

    # --- TURN 1: Establish Context ---
    print("\n🗣️  TURN 1: 'I want to inquire about a Personal Loan'")
    msg_1 = "I want to inquire about a Personal Loan"

    result_1 = await coordinator.process_message(
        message=msg_1,
        customer_id=customer_id,
        conversation_id=conversation_id
    )

    print(f"   🤖 Agent: {result_1['agent']}")
    print(f"   ✅ Intent: {result_1['intent']}")
    print(f"   📄 Response: {result_1['response'][:50]}...")

    # --- TURN 2: Contextual Query ---
    # This message is ambiguous without memory.
    # "That" refers to the loan from Turn 1.
    print("\n🗣️  TURN 2: 'What is the interest rate for that?'")
    msg_2 = "What is the interest rate for that?"

    result_2 = await coordinator.process_message(
        message=msg_2,
        customer_id=customer_id,
        conversation_id=conversation_id
    )

    print(f"   🤖 Agent: {result_2['agent']}")
    print(f"   🎯 Intent: {result_2['intent']}")
    print(f"   📄 Response: {result_2['response'][:50]}...")

    # --- VERIFICATION ---
    print("\n" + "="*60)
    print("RESULTS:")

    # Check if Turn 2 was classified as 'loan_inquiry' (Success) or 'general_inquiry' (Fail)
    if result_2['intent'] in ['loan_inquiry', 'product_inquiry']:
        print("✅ PASS: System remembered context! 'That' was correctly linked to Loans.")
    else:
        print(f"❌ FAIL: System lost context. Classified as '{result_2['intent']}' instead of loan/product.")

if __name__ == "__main__":
    asyncio.run(main())
