import asyncio
from app.agents.compliance_checker import ComplianceCheckerAgent

async def test_compliance():
    # Create agent
    agent = ComplianceCheckerAgent()

    # Test scenarios
    scenarios = [
        {
            "name": "Compliant message",
            "content": "Our Fixed Rate Mortgage offers rates from 3.99% APR. "
                      "Subject to status and affordability assessment.",
            "product_type": "loan",
        },
        {
            "name": "Non-compliant (guaranteed)",
            "content": "Guaranteed returns with zero risk! Can't lose!",
            "product_type": "investment",
        },
        {
            "name": "Missing disclaimer",
            "content": "Apply for a credit card today! Low interest rates.",
            "product_type": "credit",
        },
        {
            "name": "Sensitive topic",
            "content": "If you're struggling with debt, we can help.",
            "product_type": "loan",
        },
    ]

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Test: {scenario['name']}")
        print(f"{'='*60}")
        print(f"Content: {scenario['content']}")
        print(f"Product Type: {scenario['product_type']}")

        response = await agent.process(
            {"content": scenario["content"]},
            {"product_type": scenario["product_type"]}
        )

        print(f"\nResult:\n{response.content}")
        print(f"\nCompliant: {response.metadata['is_compliant']}")

        if response.metadata['issues']:
            print(f"Issues: {response.metadata['issues']}")

        if response.metadata['required_disclaimers']:
            print(f"Required Disclaimers:")
            for disclaimer in response.metadata['required_disclaimers']:
                print(f"  - {disclaimer}")

if __name__ == "__main__":
    asyncio.run(test_compliance())
