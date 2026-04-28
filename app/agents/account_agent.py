from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from groq import AsyncGroq
from langfuse import observe
from pydantic import BaseModel, Field
import json

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import AccountService, CustomerService, TransactionService

# ============================================================================
# ENTERPRISE SCHEMAS
# ============================================================================


class AccountQueryAnalysis(BaseModel):
    """Strict schema for determining what the user wants to know about their account."""

    query_type: Literal[
        "balance", "transactions", "statement", "details", "general"
    ] = Field(description="The exact type of account query the user is making.")


# ============================================================================
# ACCOUNT AGENT
# ============================================================================


class AccountAgent(BaseAgent):
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        account_service: AccountService = None,
        customer_service: CustomerService = None,
        transaction_service: TransactionService = None,
        **kwargs,
    ):
        super().__init__(name="account_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        if not all([account_service, customer_service, transaction_service]):
            raise ValueError("AccountAgent requires DB-backed services.")

        self.account_service = account_service
        self.customer_service = customer_service
        self.transaction_service = transaction_service

    def _get_description(self) -> str:
        return "Account Agent - Handles customer account balances, transactions, and statements."

    def _get_capabilities(self) -> List[str]:
        return [
            "Balance retrieval",
            "Transaction history",
            "Account statements",
            "Account details",
        ]

    def _format_currency(self, amount: float) -> str:
        return f"£{amount:,.2f}"

    def _friendly_account_type(self, acct_type: Any) -> str:
        key = str(acct_type).lower().split(".")[-1] if acct_type else ""
        mapping = {
            "current": "Standard Current Account",
            "savings": "High-Yield Savings",
            "loan": "Personal Loan",
            "credit": "Platinum Credit Card",
        }
        return mapping.get(key, "General Account")

    def _friendly_date(self, date_val: Any) -> str:
        if not date_val:
            return "N/A"
        if isinstance(date_val, str):
            try:
                date_val = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            except Exception:
                return date_val
        return date_val.strftime("%d %b %Y")

    def _format_history(
        self, context: Optional[Dict[str, Any]], max_turns: int = 5
    ) -> str:
        """Extracts and formats recent conversation history for the LLM prompt."""
        if not context or "conversation_history" not in context:
            return ""
        history = context["conversation_history"][-max_turns:]
        if not history:
            return ""

        formatted = []
        for msg in history:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")

        return "PREVIOUS CONVERSATION HISTORY:\n" + "\n".join(formatted) + "\n\n"

    @observe(name="AccountAgent")
    async def process(
        self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        self.log_request(input_data)

        try:
            await self.validate_input(input_data)
            customer_id = input_data.get("customer_id")
            message = input_data.get("message", "")

            if not customer_id:
                raise ValueError("Unauthorized: customer_id is required.")

            # 1. AI Intent Extraction
            query_type = await self._determine_query_type(message, context)

            # 2. Fetch Raw Database Data
            async with (
                self.customer_service as cust_svc,
                self.account_service as acct_svc,
                self.transaction_service as txn_svc,
            ):
                raw_data = await self._fetch_real_data(
                    cust_svc, acct_svc, txn_svc, str(customer_id), query_type
                )

            # 3. AI Conversational Generation
            conversational_response = await self._generate_conversational_response(
                message, raw_data, context
            )

            response = self.create_response(
                content=conversational_response,
                metadata={
                    "query_type": query_type,
                    "account_data": raw_data.get("data"),
                    "data_points": raw_data.get("data_points", []),
                },
                confidence=0.95,
            )
            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Account query error: {e}")
            return self.create_response(
                content="I apologize, but I am currently experiencing technical difficulties retrieving your account information. Please try again later.",
                metadata={"error": "internal_system_error"},
                confidence=0.0,
            )

    async def _determine_query_type(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Uses LLM structured output with Zero-Shot formatting to flawlessly identify user intent."""
        history_str = self._format_history(context)
        prompt = f"""
        {history_str}
        Analyze the following user banking query: "{message}"

        Determine if they are asking for:
        - "balance" (how much money they have)
        - "transactions" (recent activity, history, purchases)
        - "statement" (official document, PDF request)
        - "details" (account number, status, open date)
        - "general" (rules, policies, or general greetings)

        You must respond with a single valid JSON object. Do NOT wrap it in a list or array.
        It must contain exactly one key: "query_type".

        Example Output:
        {{
            "query_type": "balance"
        }}
        """
        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            # We still use Pydantic to strictly validate the output!
            analysis = AccountQueryAnalysis.model_validate_json(
                response.choices[0].message.content
            )
            return analysis.query_type

        except Exception as e:
            self.logger.error(f"LLM Intent Error: {e}")
            return "general"

    async def _generate_conversational_response(
        self,
        user_message: str,
        raw_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Feeds raw DB JSON to the LLM to generate a natural, helpful response."""
        if raw_data.get("error"):
            return "I'm sorry, I couldn't locate your active account details at this moment."

        history_str = self._format_history(context)

        # 🛠️ FIX: Give the bank a name (e.g., Nexus Bank) and forbid placeholders!
        prompt = f"""
        You are a highly professional banking AI assistant for One Bank.

        {history_str}

        CURRENT USER MESSAGE: "{user_message}"

        Here is the securely retrieved raw data from their bank account:
        {json.dumps(raw_data.get("data", {}), indent=2)}

        Task:
        Formulate a polite, clear, and professional response to the user answering their question using ONLY this data.
        Ensure numbers look like currency where appropriate. Do not hallucinate any data not present in the JSON.
        Sign off your message natively as One Bank. NEVER use brackets or placeholders like [Your Bank's Name].
        """
        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"LLM Generation Error: {e}")
            return "I have retrieved your data, but experienced an issue formatting it. Please check your online portal."

    async def _fetch_real_data(
        self, cust_svc, acct_svc, txn_svc, customer_id: str, query_type: str
    ) -> Dict[str, Any]:
        """Strictly fetches data using specific repository lookups."""

        # FIX: Use the repository to search by the string 'CUST-000001'
        clean_id = str(customer_id).replace("CUST-", "")
        formatted_customer_id = f"CUST-{clean_id.zfill(6)}"
        customer = await cust_svc.repo.get_by_customer_id(formatted_customer_id)
        if not customer:
            return {"error": "customer_not_found"}

        accounts = await acct_svc.get_accounts_by_customer(formatted_customer_id)
        if not accounts:
            return {"error": "no_accounts_found"}

        acct = accounts[0]

        if query_type == "balance" or query_type == "details":
            # 🛠️ FIX: Loop through ALL accounts and pass them to the AI
            accounts_data = []
            for acc in accounts:
                accounts_data.append(
                    {
                        "account_number": getattr(acc, "account_number", "N/A"),
                        "account_type": self._friendly_account_type(
                            getattr(acc, "type", None)
                        ),
                        "balance": self._format_currency(
                            float(getattr(acc, "balance", 0.0))
                        ),
                        "status": "Active",
                        "opened_on": self._friendly_date(
                            getattr(acc, "created_at", None)
                        ),
                    }
                )

            return {
                "data": {"portfolio": accounts_data},
                "data_points": [query_type],
            }
        elif query_type == "transactions":
            # FIX: We need the internal integer 'id' for transactions
            account_id = getattr(acct, "id", None)
            all_transactions = await txn_svc.get_transactions_by_account(
                account_id, limit=5
            )

            txns = [
                {
                    "description": getattr(t, "description", "Unknown"),
                    "amount": self._format_currency(float(getattr(t, "amount", 0.0))),
                    "date": self._friendly_date(
                        getattr(t, "date", None) or getattr(t, "transaction_date", None)
                    ),
                }
                for t in all_transactions
            ]

            return {
                "data": {"recent_transactions": txns},
                "data_points": ["transactions"],
            }

        elif query_type == "statement":
            return {
                "data": {
                    "account_number": getattr(acct, "account_number", "N/A"),
                    "email": getattr(customer, "email", "your registered email"),
                    "statement_status": "Generated and sent",
                },
                "data_points": ["statement_generated"],
            }

        return {"data": {"note": "Account verified. Awaiting specific inquiry."}}
