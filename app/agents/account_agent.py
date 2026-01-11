from typing import Dict, Any, Optional, List
from datetime import datetime
from groq import AsyncGroq

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import AccountService, CustomerService, TransactionService

class AccountAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None
                 ,account_service: AccountService = None,
        customer_service: CustomerService = None,
        transaction_service: TransactionService = None,
        **kwargs):
        super().__init__(name="account_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        if account_service is None or customer_service is None or transaction_service is None:
            raise ValueError("AccountAgent requires DB-backed services (inject AccountService/CustomerService/TransactionService).")

        self.account_service = account_service
        self.customer_service = customer_service
        self.transaction_service = transaction_service

    def _get_description(self) -> str:
        return (
            "Account Agent - Handles customer account inquiries including "
            "balance checks, transaction history, account statements, and operations."
        )

    def _get_capabilities(self) -> List[str]:
        return [
            "Account balance retrieval",
            "Transaction history lookup",
            "Account statement generation",
            "Account detail queries",
            "Natural language account information",
        ]

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        self.log_request(input_data)

        try:
            await self.validate_input(input_data)

            customer_id = input_data.get("customer_id")
            message = input_data.get("message", "")
            if not customer_id:
                raise ValueError("customer_id is required")

            query_type = self._determine_query_type(message)
            result = await self._fetch_real_data(customer_id, query_type, message)
            response = self.create_response(
                content=result["response"],
                metadata={
                    "query_type": query_type,
                    "account_data": result.get("data"),
                    "data_points": result.get("data_points", []),
                },
                confidence=0.95,
            )
            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Account query error: {e}")
            return self.create_response(
                content=f"I couldn't retrieve your account information. Error: {str(e)}",
                metadata={"error": str(e)},
                confidence=0.0,
            )

    def _determine_query_type(self, message: str) -> str:
        message_lower = message.lower()
        if any(word in message_lower for word in ["balance", "how much", "account total", "have"]):
            return "balance"
        elif any(word in message_lower for word in ["transaction", "history", "recent", "activity"]):
            return "transactions"
        elif any(word in message_lower for word in ["statement", "download", "pdf", "email"]):
            return "statement"
        elif any(word in message_lower for word in ["details", "information", "account info"]):
            return "details"
        else:
            return "general"

    async def _fetch_real_data(self, customer_id: int, query_type: str, message: str) -> Dict[str, Any]:
        """
        Fetch real data from database services.
        """
        try:
            # 1) Customer lookup uses INTERNAL PK (customers.id: int)
            customer = await self.customer_service.get_customer(customer_id)
            if not customer:
                return {"response": f"Customer {customer_id} not found", "data": {}, "data_points": []}

            # 2) Accounts lookup uses EXTERNAL customer id (accounts.customer_id: varchar)
            external_customer_id = getattr(customer, "customer_id", None)
            if not external_customer_id:
                return {
                    "response": f"Customer {customer_id} is missing external customer_id",
                    "data": {},
                    "data_points": [],
                }

            # Helper: safely pull account fields that differ by schema
            def _account_summary(acct):
                return {
                    "account_number": getattr(acct, "account_number", None),
                    "type": getattr(acct, "type", None),  # <-- real column name is `type`
                    "status": getattr(acct, "status", None),
                    "balance": float(getattr(acct, "balance", 0.0) or 0.0),
                    "created_at": getattr(acct, "created_at", None),
                }

            if query_type == "balance":
                accounts = await self.account_service.get_accounts_by_customer(external_customer_id)
                if not accounts:
                    response = (
                        "Your current account balance is 0.00.\n\n"
                        "Account: N/A\n"
                        "Account Type: N/A\n"
                        f"Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    return {
                        "response": response,
                        "data": {"balance": 0.0, "account_number": None, "type": None},
                        "data_points": ["balance", "account_number", "type"],
                    }

                acct = accounts[0]
                acct_num = getattr(acct, "account_number", None)
                acct_type = getattr(acct, "type", None)
                balance = float(getattr(acct, "balance", 0.0) or 0.0)

                response = (
                    f"Your current account balance is {balance:,.2f}.\n\n"
                    f"Account: {acct_num or 'N/A'}\n"
                    f"Account Type: {acct_type or 'N/A'}\n"
                    f"Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                return {
                    "response": response,
                    "data": {"balance": balance, "account_number": acct_num, "type": acct_type},
                    "data_points": ["balance", "account_number", "type"],
                }

            elif query_type == "transactions":
                accounts = await self.account_service.get_accounts_by_customer(external_customer_id)
                if not accounts:
                    return {"response": f"No accounts found for customer {customer_id}", "data": {}, "data_points": []}

                acct = accounts[0]
                account_id = getattr(acct, "id", None)
                if account_id is None:
                    return {"response": "Account record missing id", "data": {}, "data_points": []}

                # Note: this service actually expects account_id (despite method name) in your codebase
                transactions = await self.transaction_service.get_transactions_by_account(account_id, limit=10)

                response = "Your recent transactions (last 10):\n\n"
                for i, txn in enumerate(transactions, 1):
                    response += (
                        f"{i}. {getattr(txn, 'description', 'N/A')}\n"
                        f" Amount: {float(getattr(txn, 'amount', 0.0) or 0.0):,.2f}\n"
                        f" Date: {getattr(txn, 'transaction_date', 'N/A')}\n"
                        f" Balance: {float(getattr(txn, 'balance_after', 0.0) or 0.0):,.2f}\n\n"
                    )

                return {
                    "response": response,
                    "data": {
                        "account": _account_summary(acct),
                        "transactions": [
                            {
                                "description": getattr(t, "description", None),
                                "amount": getattr(t, "amount", None),
                                "date": getattr(t, "transaction_date", None),
                            }
                            for t in transactions
                        ],
                    },
                    "data_points": ["transactions", "dates", "amounts"],
                }

            elif query_type == "statement":
                accounts = await self.account_service.get_accounts_by_customer(external_customer_id)
                acct = accounts[0] if accounts else None
                account_number = getattr(acct, "account_number", None) if acct else None

                response = (
                    f"Statement Request for Account {account_number or 'N/A'}\n\n"
                    "Your account statement has been generated.\n"
                    f"A PDF will be emailed to {getattr(customer, 'email', 'your email')} shortly.\n\n"
                    "You can also download it from your online banking portal:\n"
                    "- Log in to your account\n"
                    "- Go to Documents > Statements\n"
                    "- Select the date range\n"
                    "- Click Download PDF\n\n"
                    "If you need help, contact us at support@bank.com"
                )

                return {
                    "response": response,
                    "data": {"account_number": account_number, "email": getattr(customer, "email", None)},
                    "data_points": ["statement_generated", "email", "account_number"],
                }

            elif query_type == "details":
                accounts = await self.account_service.get_accounts_by_customer(external_customer_id)
                if not accounts:
                    return {"response": f"No accounts found for customer {customer_id}", "data": {}, "data_points": []}

                acct = accounts[0]
                acct_num = getattr(acct, "account_number", None)
                acct_type = getattr(acct, "type", None)
                created_at = getattr(acct, "created_at", None)  # prefer created_at over created_date

                response = (
                    f"Account Details for Customer {customer_id}\n\n"
                    f"Account Number: {acct_num or 'N/A'}\n"
                    f"Account Type: {acct_type or 'N/A'}\n"
                    f"Current Balance: {float(getattr(acct, 'balance', 0.0) or 0.0):,.2f}\n"
                    f"Account Status: {getattr(acct, 'status', 'N/A')}\n"
                    f"Created: {created_at or 'N/A'}\n"
                    f"Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "Contact information on file:\n"
                    f"Email: {getattr(customer, 'email', 'N/A')}\n"
                    f"Phone: {getattr(customer, 'phone', 'N/A')}"
                )

                return {
                    "response": response,
                    "data": {
                        "account_number": acct_num,
                        "type": acct_type,
                        "balance": float(getattr(acct, "balance", 0.0) or 0.0),
                        "status": getattr(acct, "status", None),
                        "created_at": created_at,
                    },
                    "data_points": ["account_number", "type", "balance", "status", "created_at"],
                }

            else:
                accounts = await self.account_service.get_accounts_by_customer(external_customer_id)
                response = f"Account information for customer {customer_id}. How else can I help with your account?"
                return {
                    "response": response,
                    "data": {"account_count": len(accounts) if accounts else 0},
                    "data_points": ["account_info"],
                }

        except Exception as e:
            self.logger.error(f"Error fetching real data: {e}")
            return {"response": f"Error retrieving account information: {str(e)}", "data": {}, "data_points": []}
