"""
Database Seeding Script

Populates database with sample data for development and testing.
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import text  # <--- Added import

from app.database import AsyncSessionLocal
from app.services.customer import CustomerService
from app.services.conversation import ConversationService
from app.services.message import MessageService
from app.models.conversation import ConversationChannel, ConversationStatus
from app.models.message import MessageRole

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# SAMPLE DATA
# ============================================================================

SAMPLE_CUSTOMERS = [
    {
        "customer_id": "CUST-001",
        "first_name": "John",
        "last_name": "Smith",
        "email": "john.smith@example.com",
        "phone": "+44123456789",
        "is_vip": True,
    },
    {
        "customer_id": "CUST-002",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone": "+44987654321",
        "is_vip": False,
    },
    {
        "customer_id": "CUST-003",
        "first_name": "Robert",
        "last_name": "Johnson",
        "email": "robert.johnson@example.com",
        "phone": "+44111222333",
        "is_vip": True,
    },
]

SAMPLE_CONVERSATIONS = [
    {
        "title": "Mortgage Application Inquiry",
        "channel": ConversationChannel.WEB,
        "intent": "loan_inquiry",
    },
    {
        "title": "Account Balance Question",
        "channel": ConversationChannel.MOBILE,
        "intent": "account_balance",
    },
    {
        "title": "Credit Card Application",
        "channel": ConversationChannel.WEB,
        "intent": "credit_card",
    },
]

SAMPLE_MESSAGES = [
    # Conversation 1 messages
    [
        {
            "role": MessageRole.CUSTOMER,
            "content": "I'm interested in applying for a mortgage. What are the requirements?",
            "intent": "loan_inquiry",
            "sentiment": "neutral",
            "confidence_score": 95,
        },
        {
            "role": MessageRole.AGENT,
            "content": "I'd be happy to help you with your mortgage inquiry. Let me provide you with the key requirements...",
            "agent_name": "product_recommender",
        },
        {
            "role": MessageRole.CUSTOMER,
            "content": "What interest rates do you currently offer?",
            "intent": "loan_inquiry",
            "sentiment": "positive",
            "confidence_score": 92,
        },
    ],
    # Conversation 2 messages
    [
        {
            "role": MessageRole.CUSTOMER,
            "content": "What is my current account balance?",
            "intent": "account_balance",
            "sentiment": "neutral",
            "confidence_score": 98,
        },
        {
            "role": MessageRole.AGENT,
            "content": "I can help you check your account balance. Let me retrieve that information...",
            "agent_name": "account_agent",
        },
    ],
]

# ============================================================================
# SEEDING FUNCTIONS
# ============================================================================

async def seed_customers() -> list:
    """
    Seed sample customers.

    Returns:
        list: Created customer IDs
    """
    logger.info("Seeding customers...")

    customer_ids = []

    async with CustomerService() as service:
        for data in SAMPLE_CUSTOMERS:
            try:
                customer = await service.create_customer(**data)
                customer_ids.append(customer.id)
                logger.info(f"Created customer: {customer.full_name} ({customer.email})")
            except ValueError as e:
                logger.warning(f"Skipped customer {data['email']}: {e}")

    logger.info(f"Seeded {len(customer_ids)} customers")
    return customer_ids

async def seed_conversations(customer_ids: list) -> list:
    """
    Seed sample conversations.

    Args:
        customer_ids: List of customer IDs

    Returns:
        list: Created conversation IDs
    """
    logger.info("Seeding conversations...")

    conversation_ids = []

    async with ConversationService() as service:
        for i, data in enumerate(SAMPLE_CONVERSATIONS):
            # Assign to customers in round-robin fashion
            customer_id = customer_ids[i % len(customer_ids)]

            conversation = await service.start_conversation(
                customer_id=customer_id,
                title=data["title"],
                channel=data["channel"]
            )

            # Update intent if provided
            if "intent" in data:
                async with AsyncSessionLocal() as session:
                    conv = await session.get(type(conversation), conversation.id)
                    conv.intent = data["intent"]
                    await session.commit()

            conversation_ids.append(conversation.id)
            logger.info(f"Created conversation: {conversation.title}")

    logger.info(f"Seeded {len(conversation_ids)} conversations")
    return conversation_ids

async def seed_messages(conversation_ids: list):
    """
    Seed sample messages.

    Args:
        conversation_ids: List of conversation IDs
    """
    logger.info("Seeding messages...")

    message_count = 0

    async with MessageService() as service:
        for i, messages in enumerate(SAMPLE_MESSAGES):
            if i >= len(conversation_ids):
                break

            conversation_id = conversation_ids[i]

            for msg_data in messages:
                message = await service.add_message(
                    conversation_id=conversation_id,
                    **msg_data
                )
                message_count += 1
                logger.info(f"Created message: {msg_data['role'].value} - {msg_data['content'][:50]}...")

    logger.info(f"Seeded {message_count} messages")

async def clear_database():
    """
    Clear all data from database.

    WARNING: This will delete ALL data!
    """
    logger.warning("Clearing database...")

    async with AsyncSessionLocal() as session:
        # Delete in reverse order of foreign keys
        # Wraps SQL strings in text() to avoid SQLAlchemy errors
        await session.execute(text("DELETE FROM messages"))
        await session.execute(text("DELETE FROM conversations"))
        await session.execute(text("DELETE FROM customers"))
        await session.commit()

    logger.info("Database cleared")

# ============================================================================
# MAIN SEEDING FUNCTION
# ============================================================================

async def seed_all(clear_first: bool = False):
    """
    Seed all sample data.

    Args:
        clear_first: Whether to clear existing data first
    """
    try:
        if clear_first:
            await clear_database()

        logger.info("Starting database seeding...")

        # Seed in order of dependencies
        customer_ids = await seed_customers()
        conversation_ids = await seed_conversations(customer_ids)
        await seed_messages(conversation_ids)

        logger.info("✅ Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error seeding database: {e}", exc_info=True)
        raise

# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    # Check for --clear flag
    clear_first = "--clear" in sys.argv

    # Run seeding
    asyncio.run(seed_all(clear_first=clear_first))
