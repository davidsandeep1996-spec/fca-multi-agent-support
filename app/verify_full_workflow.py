"""
VERIFY FULL WORKFLOW
Tests the complete chain: Coordinator -> Workflow -> Agents -> DB
"""
import asyncio
import logging
import sys
from app.coordinator.agent_coordinator import AgentCoordinator
from app.database import check_db_connection

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("workflow_test")

async def main():
    print("\n" + "="*60)
    print("🚦 FULL SYSTEM WORKFLOW TEST")
    print("="*60)

    # 0. Check DB Connection First
    print("🔌 Checking Database Connection...")
    if not await check_db_connection():
        print("❌ DB Connection Failed! Ensure Postgres is running.")
        sys.exit(1)
    print("✅ DB Connected.")

    # 1. Initialize Coordinator
    coordinator = AgentCoordinator()
    print("✅ Coordinator Initialized.")

    # 2. Define Test Scenarios
    scenarios = [
        {
            "name": "General Inquiry (FAQ)",
            "message": "How do I open an account?",
            "expected_agent": "general",
            "check": lambda res: res['intent'] == "general_inquiry"
        },
        {
            "name": "Product Inquiry (DB Read + Compliance)",
            "message": "I want a personal loan",
            "expected_agent": "product",
            "check": lambda res: "loan" in str(res['response']).lower()
        },
        {
            "name": "Complaint (Escalation + Pydantic Ticket)",
            "message": "I want to file a complaint about a stolen card",
            "expected_agent": "human",
            "check": lambda res: res['escalated'] is True and res['escalation_id'].startswith("ESC-")
        },
        {
            "name": "Account Inquiry (DB Read)",
            "message": "What is my account balance?",
            "expected_agent": "account",
            "check": lambda res: "balance" in str(res['response']).lower()
        }
    ]

    # 3. Run Tests
    customer_id = 1
    conversation_id = 100

    for i, test in enumerate(scenarios, 1):
        print(f"\n📝 [Test {i}] {test['name']}")
        print(f"   👤 User: '{test['message']}'")

        try:
            # The Critical Call
            result = await coordinator.process_message(
                message=test['message'],
                customer_id=customer_id,
                conversation_id=conversation_id
            )

            agent_used = result["agent"]
            response_text = result["response"]

            print(f"   🤖 Agent Used: {agent_used}")
            print(f"   📄 Response: {response_text[:80].replace(chr(10), ' ')}...")

            # Validation
            if agent_used == test["expected_agent"]:
                if test["check"](result):
                    print("   ✅ PASS: Routing & Logic Correct")
                else:
                    print("   ⚠️  PARTIAL PASS: Agent correct, but check logic failed.")
            else:
                print(f"   ❌ FAIL: Routed to {agent_used}, expected {test['expected_agent']}")
                print(f"   (Debug: Intent was {result.get('intent')})")

        except Exception as e:
            print(f"   ❌ CRASH: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
