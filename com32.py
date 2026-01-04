from app.services import CustomerService, ConversationService
from app.models.conversation import ConversationChannel
import asyncio

async def test():
    # Create customer
    async with CustomerService() as service:
        customer = await service.create_customer(
            customer_id="CUST-002",
            first_name="John",
            last_name="Smith",
            email="john1@example.com"
        )
        print(f"Created customer: {customer.id}")

    # Start conversation
    async with ConversationService() as service:
        conv = await service.start_conversation(
            customer_id=customer.id,
            title="Loan Inquiry",
            channel=ConversationChannel.WEB
        )
        print(f"Started conversation: {conv.id}")

asyncio.run(test())

asyncio.run(test())
