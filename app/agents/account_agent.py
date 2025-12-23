from typing import Dict, Any, Optional, List
from datetime import datetime
from groq import AsyncGroq

from app.agents.base import BaseAgent, AgentConfig, AgentResponse


class AccountAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(name="account_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

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
            result = self._generate_mock_response(customer_id, query_type, message)

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

    def _generate_mock_response(
        self, customer_id: int, query_type: str, message: str
    ) -> Dict[str, Any]:
        if query_type == "balance":
            balance = 5432.50
            response = (
                f"Your current account balance is £{balance:,.2f}.\n\n"
                f"Account: ACC-001-{customer_id}\n"
                f"Account Type: Current\n"
                f"Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return {
                "response": response,
                "data": {
                    "balance": balance,
                    "account_number": f"ACC-001-{customer_id}",
                    "account_type": "Current",
                },
                "data_points": ["balance", "account_number", "account_type"],
            }

        if query_type == "transactions":
            response = (
                "Your recent transactions (last 30 days):\n\n"
                "1. Sainsbury's Grocery\n"
                "   Amount: -£87.50\n"
                "   Date: 2025-12-21 14:30\n"
                "   Balance: £5,432.50\n\n"
                "2. Salary Deposit\n"
                "   Amount: +£2,500.00\n"
                "   Date: 2025-12-20 09:15\n"
                "   Balance: £5,520.00\n\n"
                "3. Amazon Purchase\n"
                "   Amount: -£45.99\n"
                "   Date: 2025-12-19 18:45\n"
                "   Balance: £3,020.00"
            )
            return {
                "response": response,
                "data": {
                    "transactions": [
                        {"description": "Sainsbury's", "amount": -87.50, "date": "2025-12-21"},
                        {"description": "Salary", "amount": 2500.00, "date": "2025-12-20"},
                        {"description": "Amazon", "amount": -45.99, "date": "2025-12-19"},
                    ]
                },
                "data_points": ["transactions", "dates", "amounts"],
            }

        if query_type == "statement":
            response = (
                f"Statement Request for Account ACC-001-{customer_id}\n\n"
                f"Your account statement has been generated.\n"
                f"A PDF will be emailed to customer@example.com shortly.\n\n"
                f"You can also download it from your online banking portal:\n"
                f"- Log in to your account\n"
                f"- Go to Documents > Statements\n"
                f"- Select the date range\n"
                f"- Click Download PDF\n\n"
                f"If you need help, contact us at support@bank.com"
            )
            return {
                "response": response,
                "data": {
                    "account_number": f"ACC-001-{customer_id}",
                    "email": "customer@example.com",
                },
                "data_points": ["statement_generated", "email", "account_number"],
            }

        if query_type == "details":
            response = (
                f"Account Details for Customer {customer_id}\n\n"
                f"Account Number: ACC-001-{customer_id}\n"
                f"Account Type: Current\n"
                f"Current Balance: £5,432.50\n"
                f"Account Status: Active\n"
                f"Created: 2023-01-15\n"
                f"Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Contact information on file:\n"
                f"Email: customer@example.com\n"
                f"Phone: +44 7700 900000"
            )
            return {
                "response": response,
                "data": {
                    "account_number": f"ACC-001-{customer_id}",
                    "account_type": "Current",
                    "balance": 5432.50,
                    "status": "active",
                },
                "data_points": ["account_number", "account_type", "balance", "status"],
            }

        response = (
            f"Account information for customer {customer_id}. "
            f"How else can I help with your account?"
        )
        return {
            "response": response,
            "data": {"account_number": f"ACC-001-{customer_id}"},
            "data_points": ["account_info"],
        }
