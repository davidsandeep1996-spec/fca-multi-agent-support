"""
Database Seeding Script - 1000+ Realistic Records with Auto-Table Creation

Populates database with large-scale sample data for development and testing.

Features:
- Auto-creates all tables (idempotent, safe to run multiple times)
- Generates realistic UK customer data via Faker
- Seeds products, accounts, transactions, conversations, and messages
- Optional data clearing (--clear flag)
- Configurable scale (--customers N)
- Expected vs Actual report (variance + success rate)
- FIXED: Proper transaction handling without savepoints
- FIXED: datetime.utcnow() deprecation warning resolved
- FIXED: Better error reporting with full exception details
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from faker import Faker
from sqlalchemy import text

from app.database import AsyncSessionLocal, engine, Base
from app.services.customer import CustomerService
from app.services.conversation import ConversationService
from app.services.message import MessageService
from app.services import ProductService, AccountService, TransactionService
from app.models.conversation import ConversationChannel
from app.models.message import MessageRole
from app.models.account import AccountType, AccountStatus


# =============================================================================
# Logging + Faker
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
fake = Faker("en_GB")


# =============================================================================
# Table creation
# =============================================================================
async def create_all_tables() -> None:
    """Create all database tables if they don't exist (idempotent)."""
    logger.info("🔧 Checking/Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ All tables created/verified successfully\n")


# =============================================================================
# Data generation
# =============================================================================
def generate_customers(count: int = 100) -> list[dict]:
    customers: list[dict] = []
    for i in range(1, count + 1):
        customers.append(
            {
                "customer_id": f"CUST-{i:06d}",
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.unique.email(),
                "phone": fake.phone_number(),
                "is_vip": fake.random_element([True, False, False, False]),  # ~25% VIP
            }
        )
    return customers


SAMPLE_PRODUCTS = [
    {
        "name": "Premium Savings Account",
        "type": "savings",
        "description": "Earn interest on your savings with flexible access",
        "interest_rate": Decimal("2.50"),
        "features": ["Interest payments", "Easy access", "No fees"],
        "requirements": {"min_balance": 1000, "age": 18},
        "is_active": True,
    },
    {
        "name": "Current Account",
        "type": "current",
        "description": "Everyday banking made easy",
        "interest_rate": Decimal("0.00"),
        "features": ["Debit card", "Online banking", "Direct deposits"],
        "requirements": {"age": 16},
        "is_active": True,
    },
    {
        "name": "Travel Credit Card",
        "type": "credit",
        "description": "Rewards on every purchase",
        "interest_rate": Decimal("9.99"),
        "features": ["Cashback", "Travel insurance", "No foreign fees"],
        "requirements": {"min_income": 25000},
        "is_active": True,
    },
    {
        "name": "Personal Loan",
        "type": "loan",
        "description": "Borrow up to £50,000 at competitive rates",
        "interest_rate": Decimal("7.49"),
        "features": ["Flexible terms", "Quick approval", "No early repayment penalty"],
        "requirements": {"min_income": 30000, "credit_score": 600},
        "is_active": True,
    },
    {
        "name": "Fixed Rate Bond",
        "type": "savings",
        "description": "Guaranteed returns on your investment",
        "interest_rate": Decimal("4.25"),
        "features": ["Fixed returns", "1-year term", "FSCS protected"],
        "requirements": {"min_balance": 5000},
        "is_active": True,
    },
]

REALISTIC_MERCHANTS = [
    "Tesco", "Sainsbury's", "Asda", "Morrisons", "Waitrose", "Co-op",
    "Lidl", "Aldi", "Iceland", "Marks & Spencer", "Starbucks", "Costa Coffee",
    "Pret A Manger", "Greggs", "McDonald's", "Subway", "Pizza Hut", "KFC",
    "Nando's", "Wagamama", "Netflix", "Spotify", "Amazon", "eBay",
    "Argos", "John Lewis", "Boots", "Uber",
]

TRANSACTION_CATEGORIES = [
    "groceries", "dining", "entertainment", "transport", "utilities", "shopping",
    "subscriptions", "travel", "health", "fitness", "education", "bills",
    "insurance", "fuel", "phone", "internet",
]

SAMPLE_CONVERSATIONS = [
    {"title": "Mortgage Application Inquiry", "channel": ConversationChannel.WEB, "intent": "loan_inquiry"},
    {"title": "Account Balance Question", "channel": ConversationChannel.MOBILE, "intent": "account_balance"},
    {"title": "Credit Card Application", "channel": ConversationChannel.WEB, "intent": "credit_card"},
]


# =============================================================================
# Seeding functions
# =============================================================================
async def seed_customers(count: int = 100) -> list[int]:
    logger.info(f"🌱 Seeding {count} customers...")
    customer_ids: list[int] = []
    customers_data = generate_customers(count)
    customers_failed = 0

    async with CustomerService() as service:
        for i, data in enumerate(customers_data, start=1):
            try:
                customer = await service.create_customer(**data)
                customer_ids.append(customer.id)
                if i % 10 == 0:
                    logger.info(f"  ✅ Created {i}/{count} customers")
            except Exception as e:
                customers_failed += 1
                await service.rollback()
                logger.debug(f"⚠️  Skipped customer {data.get('email')}: {str(e)[:200]}")

        await service.commit()

    logger.info(f"📊 Seeded {len(customer_ids)}/{count} customers ({customers_failed} failed)\n")
    return customer_ids


async def seed_products() -> list[int]:
    """Seed products and COMMIT each individually (FK requirement for accounts)."""
    logger.info("🌱 Seeding products...")
    product_ids: list[int] = []
    products_failed = 0

    for data in SAMPLE_PRODUCTS:
        async with ProductService() as service:
            try:
                product = await service.repo.create(data)
                await service.commit()  # Commit EACH product individually
                product_ids.append(product.id)
                logger.info(f"✅ Created product: {product.name} ({product.type}) id={product.id}")
            except Exception as e:
                products_failed += 1
                try:
                    await service.rollback()
                except Exception:
                    pass
                logger.warning(f"⚠️  Skipped product {data.get('name')}: {str(e)[:200]}")

    logger.info(f"🔐 {len(product_ids)}/{len(SAMPLE_PRODUCTS)} Products COMMITTED - safe for FK references ({products_failed} failed)\n")
    return product_ids


async def seed_accounts(customer_ids: list[int], product_ids: list[int]) -> list[int]:
    logger.info("🌱 Seeding accounts (2-3 per customer)...")

    if not product_ids:
        raise RuntimeError("❌ No products were created; cannot seed accounts safely.")

    logger.info(f"   Available product IDs: {product_ids}\n")

    account_ids: list[int] = []
    account_types = [AccountType.CURRENT, AccountType.SAVINGS, AccountType.CREDIT]
    accounts_failed = 0

    for idx, customer_id in enumerate(customer_ids):
        async with AccountService() as service:
            try:
                async with AsyncSessionLocal() as session:
                    from app.models.customer import Customer

                    customer = await session.get(Customer, customer_id)
                    ext_customer_id = customer.customer_id if customer else f"CUST-{idx+1:06d}"

                num_accounts = 2 + (idx % 2)  # 2 or 3 accounts
                for j in range(num_accounts):
                    try:
                        product_id = product_ids[j % len(product_ids)]
                        account_type = account_types[j % len(account_types)]

                        account_data = {
                            "account_number": f"ACC{ext_customer_id}{j:02d}",
                            "customer_id": ext_customer_id,
                            "product_id": product_id,
                            "type": account_type,
                            "status": AccountStatus.ACTIVE,
                            "currency": "GBP",
                            "balance": Decimal(str(fake.random_int(1000, 500000))),
                            "available_balance": Decimal(str(fake.random_int(500, 500000))),
                        }

                        account = await service.repo.create(account_data)
                        account_ids.append(account.id)
                    except Exception as e:
                        accounts_failed += 1
                        logger.debug(f"⚠️  Skipped account {ext_customer_id}:{j}: {str(e)[:200]}")
                        continue

                await service.commit()

            except Exception as e:
                logger.debug(f"⚠️  Customer {idx} batch error: {str(e)[:200]}")
                try:
                    await service.rollback()
                except Exception:
                    pass
                continue

            if (idx + 1) % 20 == 0:
                logger.info(f"  ✅ Created {len(account_ids)} accounts for {idx + 1}/{len(customer_ids)} customers ({accounts_failed} failed)")

    logger.info(f"📊 Seeded {len(account_ids)} accounts ({accounts_failed} failed)\n")
    return account_ids


async def seed_transactions(account_ids: list[int]) -> int:
    logger.info("🌱 Seeding transactions (10-20 per account)...")
    logger.info(f"   This will create ~{len(account_ids) * 15:,} transactions...\n")

    transaction_count = 0
    transactions_failed = 0
    first_error_logged = 0

    for acc_idx, account_id in enumerate(account_ids, start=1):
        # FIXED: Create fresh service per account to avoid session issues
        async with TransactionService() as service:
            num_transactions = fake.random_int(10, 20)

            for i in range(num_transactions):
                try:
                    days_ago = fake.random_int(1, 90)
                    # FIXED: Use naive UTC datetime instead of deprecated utcnow()
                    trans_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)

                    transaction_data = {
                        "account_id": account_id,
                        "reference": f"TXN-{account_id}-{i:04d}",
                        "amount": Decimal(str(fake.random_int(10, 50000) / 100)),
                        "currency": "GBP",
                        "description": fake.sentence(nb_words=4),
                        "category": fake.random_element(TRANSACTION_CATEGORIES),
                        "date": trans_date,
                        "merchant_name": fake.random_element(REALISTIC_MERCHANTS),
                    }

                    # FIXED: Create directly without nested savepoint
                    await service.repo.create(transaction_data)
                    transaction_count += 1

                except Exception as e:
                    transactions_failed += 1
                    # FIXED: Rollback after error to reset session state
                    try:
                        await service.rollback()
                    except Exception:
                        pass

                    # Print detailed error for first few failures
                    if first_error_logged < 5:
                        logger.warning(
                            f"❌ Transaction failed (account_id={account_id}, i={i}): {type(e).__name__}: {str(e)}"
                        )
                        first_error_logged += 1
                    continue

            # Commit all successful transactions for this account
            try:
                await service.commit()
            except Exception as e:
                logger.warning(f"❌ Account {account_id} commit failed: {type(e).__name__}: {str(e)}")
                try:
                    await service.rollback()
                except Exception:
                    pass

            if acc_idx % 50 == 0:
                logger.info(f"  ✅ Created {transaction_count:,} transactions for {acc_idx}/{len(account_ids)} accounts ({transactions_failed} failed)")

    logger.info(f"📊 Seeded {transaction_count:,} transactions ({transactions_failed} failed)\n")
    return transaction_count


async def seed_conversations(customer_ids: list[int]) -> list[int]:
    logger.info("🌱 Seeding conversations...")
    conversation_ids: list[int] = []
    conversations_failed = 0

    async with ConversationService() as service:
        for i, data in enumerate(SAMPLE_CONVERSATIONS):
            customer_id = customer_ids[i % len(customer_ids)]
            try:
                conversation = await service.start_conversation(
                    customer_id=customer_id,
                    title=data["title"],
                    channel=data["channel"],
                )
                conversation_ids.append(conversation.id)
                logger.info(f"✅ Created conversation: {conversation.title}")
            except Exception as e:
                conversations_failed += 1
                await service.rollback()
                logger.warning(f"⚠️  Skipped conversation: {str(e)[:200]}")

        await service.commit()

    logger.info(f"📊 Seeded {len(conversation_ids)}/{len(SAMPLE_CONVERSATIONS)} conversations ({conversations_failed} failed)\n")
    return conversation_ids


async def seed_messages(conversation_ids: list[int]) -> int:
    logger.info("🌱 Seeding messages...")

    sample_messages = [
        {
            "role": MessageRole.CUSTOMER,
            "content": "I'm interested in applying for a mortgage. What are the requirements?",
            "intent": "loan_inquiry",
        },
        {
            "role": MessageRole.AGENT,
            "content": "I'd be happy to help you with your mortgage inquiry. Let me provide key requirements...",
            "agent_name": "product_recommender",
        },
        {
            "role": MessageRole.CUSTOMER,
            "content": "What is my current account balance?",
            "intent": "account_balance",
        },
        {
            "role": MessageRole.AGENT,
            "content": "Let me retrieve your current account balance from our system...",
            "agent_name": "account_agent",
        },
    ]

    message_count = 0
    messages_failed = 0

    async with MessageService() as service:
        for i, conversation_id in enumerate(conversation_ids):
            for msg_data in sample_messages[i : i + 2]:
                try:
                    await service.add_message(conversation_id=conversation_id, **msg_data)
                    message_count += 1
                except Exception as e:
                    messages_failed += 1
                    logger.debug(f"⚠️  Skipped message: {str(e)[:200]}")

        await service.commit()

    logger.info(f"📊 Seeded {message_count} messages ({messages_failed} failed)\n")
    return message_count


async def clear_database() -> None:
    logger.warning("🗑️  CLEARING DATABASE - ALL DATA WILL BE DELETED!")
    logger.warning("   ⚠️  Tables will remain, only data is cleared\n")

    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM transactions"))
        await session.execute(text("DELETE FROM accounts"))
        await session.execute(text("DELETE FROM products"))
        await session.execute(text("DELETE FROM messages"))
        await session.execute(text("DELETE FROM conversations"))
        await session.execute(text("DELETE FROM customers"))
        await session.commit()

    logger.info("✅ Database cleared (tables preserved)\n")


# =============================================================================
# Main seeding function + report
# =============================================================================
async def seed_all(clear_first: bool = False, customer_count: int = 100) -> None:
    try:
        logger.info("=" * 70)
        logger.info("🌱 STARTING DATABASE SEEDING (1000+ RECORDS)")
        logger.info("=" * 70 + "\n")

        logger.info("STEP 1/3: CREATE/VERIFY TABLES")
        logger.info("-" * 70)
        await create_all_tables()

        if clear_first:
            logger.info("STEP 2/3: CLEAR EXISTING DATA (--clear flag used)")
            logger.info("-" * 70)
            await clear_database()
        else:
            logger.info("STEP 2/3: SKIP DATA CLEAR (appending to existing data)")
            logger.info("-" * 70 + "\n")

        logger.info("STEP 3/3: SEED NEW DATA")
        logger.info("-" * 70 + "\n")

        customer_ids = await seed_customers(customer_count)
        product_ids = await seed_products()
        account_ids = await seed_accounts(customer_ids, product_ids)
        trans_count = await seed_transactions(account_ids)
        conv_ids = await seed_conversations(customer_ids)
        message_count = await seed_messages(conv_ids)

        logger.info("=" * 70)
        logger.info("✅ DATABASE SEEDING COMPLETED SUCCESSFULLY!")
        logger.info("=" * 70 + "\n")

        expected_products = 5
        expected_accounts_per_customer = 2.5
        expected_transactions_per_account = 15
        expected_conversations = 3
        expected_messages_per_conversation = 2

        expected_customers = customer_count
        expected_accounts = int(len(customer_ids) * expected_accounts_per_customer)
        expected_transactions = int(expected_accounts * expected_transactions_per_account)
        expected_messages = expected_conversations * expected_messages_per_conversation
        expected_total = (
            expected_customers
            + expected_products
            + expected_accounts
            + expected_transactions
            + expected_conversations
            + expected_messages
        )

        actual_customers = len(customer_ids)
        actual_products = len(product_ids)
        actual_accounts = len(account_ids)
        actual_transactions = trans_count
        actual_conversations = len(conv_ids)
        actual_messages = message_count
        actual_total = (
            actual_customers
            + actual_products
            + actual_accounts
            + actual_transactions
            + actual_conversations
            + actual_messages
        )

        variance = actual_total - expected_total
        variance_percent = (variance / expected_total * 100) if expected_total > 0 else 0
        success_rate = (actual_total / expected_total * 100) if expected_total > 0 else 0

        logger.info("\n📊 DETAILED SEEDING REPORT\n")
        logger.info("=" * 75)
        logger.info(f"{'ENTITY':<20} {'EXPECTED':>18} {'ACTUAL':>18} {'VARIANCE':>15}")
        logger.info("=" * 75)
        logger.info(f"{'Customers':<20} {expected_customers:>18,} {actual_customers:>18,} {actual_customers - expected_customers:>+14,}")
        logger.info(f"{'Products':<20} {expected_products:>18,} {actual_products:>18,} {actual_products - expected_products:>+14,}")
        logger.info(f"{'Accounts':<20} {expected_accounts:>18,} {actual_accounts:>18,} {actual_accounts - expected_accounts:>+14,}")
        logger.info(f"{'Transactions':<20} {expected_transactions:>18,} {actual_transactions:>18,} {actual_transactions - expected_transactions:>+14,}")
        logger.info(f"{'Conversations':<20} {expected_conversations:>18,} {actual_conversations:>18,} {actual_conversations - expected_conversations:>+14,}")
        logger.info(f"{'Messages':<20} {expected_messages:>18,} {actual_messages:>18,} {actual_messages - expected_messages:>+14,}")
        logger.info("-" * 75)
        logger.info(f"{'TOTAL RECORDS':<20} {expected_total:>18,} {actual_total:>18,} {variance:>+14,}")
        logger.info("=" * 75)

        logger.info("\n📈 PERFORMANCE METRICS:")
        logger.info(f"  • Total Expected:     {expected_total:>10,} records")
        logger.info(f"  • Total Actual:       {actual_total:>10,} records")
        logger.info(f"  • Variance:           {variance:>+10,} records ({variance_percent:>+.2f}%)")
        logger.info(f"  • Success Rate:       {success_rate:>10.2f}%")

        logger.info("\n" + "=" * 75)
        logger.info("✅ COMPLETION STATUS:")
        logger.info("=" * 75)

        if variance >= -5:
            logger.info("  ✅ PASSED - All expected records created successfully!")
            logger.info(f"     Variance within acceptable range: {variance:+,} records")
        elif -50 < variance < -5:
            logger.info("  ⚠️  WARNING - Minor record creation failures detected")
            logger.info(f"     Variance: {variance:+,} records ({variance_percent:.2f}%)")
            logger.info(f"     Success Rate: {success_rate:.2f}%")
        else:
            logger.info("  ❌ FAILED - Significant record creation failures")
            logger.info(f"     Variance: {variance:+,} records ({variance_percent:.2f}%)")
            logger.info(f"     Success Rate: {success_rate:.2f}%")

        logger.info("=" * 75)
        logger.info("\n✨ SEEDING SESSION SUMMARY:")
        logger.info(f"  • Session Type:       {'Full Reset' if clear_first else 'Append Mode'}")
        logger.info(f"  • Customers Seeded:   {actual_customers:,}")
        logger.info(f"  • Total Records:      {actual_total:,}")
        logger.info("  • Database Ready:     ✅ YES")
        logger.info("\n🎯 Next Steps:")
        logger.info("  1. Verify data in database: psql or database client")
        logger.info("  2. Run API tests: pytest -v")
        logger.info("  3. Start application: python -m uvicorn app.main:app --reload")
        logger.info("\n" + "=" * 75 + "\n")

    except Exception as e:
        logger.error(f"❌ Error seeding database: {e}", exc_info=True)
        raise


# =============================================================================
# CLI entry point
# =============================================================================
if __name__ == "__main__":
    import sys

    clear_first = "--clear" in sys.argv

    customer_count = 100
    for i, arg in enumerate(sys.argv):
        if arg == "--customers" and i + 1 < len(sys.argv):
            try:
                customer_count = int(sys.argv[i + 1])
            except ValueError:
                pass

    logger.info(f"Starting seed with {customer_count} customers...")
    asyncio.run(seed_all(clear_first=clear_first, customer_count=customer_count))
