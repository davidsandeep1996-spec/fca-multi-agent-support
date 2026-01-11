import asyncio

from app.database import AsyncSessionLocal
from app.services.account_service import AccountService
from app.services.customer import CustomerService
from app.services.transaction_service import TransactionService
from app.services.product_service import ProductService
from app.services.conversation import ConversationService  # if this exists in your project

from app.agents.account_agent import AccountAgent
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.general_agent import GeneralAgent
from app.agents.human_agent import HumanAgent


async def main():
    async with AsyncSessionLocal() as session:
        # DB-backed services
        account_svc = AccountService(db=session)
        customer_svc = CustomerService(db=session)
        txn_svc = TransactionService(db=session)
        product_svc = ProductService(db=session)

        # Agents
        account_agent = AccountAgent(
            account_service=account_svc,
            customer_service=customer_svc,
            transaction_service=txn_svc,
        )

        product_agent = ProductRecommenderAgent(product_service=product_svc)  # requires injection [file:243]

        # For a true DB test, update GeneralAgent to accept injected ProductService (recommended)
        general_agent = GeneralAgent(product_service=product_svc)  # only works if you implement injection [file:245]

        human_agent = HumanAgent(conversation_service=ConversationService(db=session))  # if your ConversationService supports db

        customer_id = 2210
        conversation_id = 1

        print("\n--- AccountAgent (balance) ---")
        print((await account_agent.process({"customer_id": customer_id, "message": "What is my balance?"})).to_dict())

        print("\n--- AccountAgent (transactions) ---")
        print((await account_agent.process({"customer_id": customer_id, "message": "Show my recent transactions"})).to_dict())

        print("\n--- ProductRecommenderAgent (DB products + LLM) ---")
        # Note: this will also call Groq; if you want DB-only, modify ProductRecommenderAgent to fetch products from product_svc
        print((await product_agent.process({"customer_id": customer_id, "message": "I want a credit card"})).to_dict())

        print("\n--- GeneralAgent (should hit FAQ, not DB unless you add DB usage) ---")
        print((await general_agent.process({"message": "What are your fees?"})).to_dict())

        print("\n--- HumanAgent escalation (DB only if ConversationService saves) ---")
        ctx = {"conversation_service": human_agent.conversation_service}
        print((await human_agent.process(
            {"message": "I want to make a complaint", "customer_id": customer_id, "conversation_id": conversation_id},
            context=ctx,
        )).to_dict())

if __name__ == "__main__":
    asyncio.run(main())
