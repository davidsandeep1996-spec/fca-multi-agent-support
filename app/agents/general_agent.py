"""
General Agent

Handles general inquiries and FAQ requests.
Provides help, information, and support.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ProductService

class GeneralAgent(BaseAgent):
    """
    General agent for FAQ and support queries.

    Provides:
    - General banking information
    - FAQ answers
    - Help and support
    - Service information
    """

    # FAQ Knowledge base
    FAQ_DATABASE = {
        "opening_account": {
            "question": "How do I open an account?",
            "answer": (
                "To open an account with us:\n"
                "1. Visit our website or mobile app\n"
                "2. Click 'Open Account'\n"
                "3. Provide personal information\n"
                "4. Verify your identity\n"
                "5. Fund your account\n\n"
                "The process takes about 10 minutes."
            ),
        },
        "contact_support": {
            "question": "How do I contact support?",
            "answer": (
                "You can contact our support team at:\n"
                "📞 Phone: +44-20-XXXX-XXXX\n"
                "📧 Email: support@fca-bank.com\n"
                "💬 Live Chat: Available 9am-6pm weekdays\n"
                "🕐 Hours: Monday-Friday, 9am-6pm GMT\n\n"
                "Our team typically responds within 24 hours."
            ),
        },

        "fees": {
            "question": "What are your account fees?",
            "answer": (
                "We offer fee-free banking:\n"
                "✅ No monthly account fees\n"
                "✅ No transfer fees (domestic)\n"
                "✅ No ATM fees at partner ATMs\n"
                "⚠️ International transfers: £10 + exchange rate\n"
                "⚠️ Overdraft charges apply\n\n"
                "See our full fee schedule at bank.com/fees"
            ),
        },
        "interest_rates": {
            "question": "What interest rates do you offer?",
            "answer": (
                "Current Interest Rates:\n"
                "💰 Savings Account: Up to 4.5% AER\n"
                "💰 Fixed Bond 1-year: 5.1% AER\n"
                "💰 Fixed Bond 3-year: 4.8% AER\n"
                "💳 Credit Cards: 21.9% APR (representative)\n"
                "📌 Mortgage: From 3.99% APR\n\n"
                "Rates subject to change. See full rates at bank.com/rates"
            ),
        },
        "security": {
            "question": "Is my money safe with you?",
            "answer": (
                "Your money is protected:\n"
                "🔒 FSCS Protected: Up to £85,000\n"
                "🔐 256-bit Encryption\n"
                "🛡️ Multi-factor Authentication\n"
                "📋 FCA Regulated\n"
                "🔍 Regular Security Audits\n\n"
                "We take security seriously."
            ),
        },
        "mobile_app": {
            "question": "What can I do in the mobile app?",
            "answer": (
                "Available features:\n"
                "✅ Check balance and transactions\n"
                "✅ Transfer money\n"
                "✅ Pay bills\n"
                "✅ Apply for products\n"
                "✅ Contact support\n"
                "✅ View statements\n"
                "✅ Manage cards\n\n"
                "Download from App Store or Google Play"
            ),
        },
    }

    def __init__(self, config: Optional[AgentConfig] = None,    product_service: ProductService = None,
    **kwargs):
        """Initialize general agent."""
        super().__init__(name="general_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)
        self.product_service = product_service or ProductService()

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        """Get agent description."""
        return (
            "General Agent - Answers general questions, FAQs, and provides "
            "support information about banking services."
        )

    def _get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        return [
            "FAQ answers",
            "General banking information",
            "Support information",
            "Account opening guidance",
            "Fee and rate information",
            "Security information",
            "Service details",
        ]

    # ========================================================================
    # CORE PROCESSING
    # ========================================================================

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Process general inquiry.

        Args:
            input_data: Must contain 'message'
            context: Optional context

        Returns:
            AgentResponse: Answer to inquiry
        """
        self.log_request(input_data)

        try:
            await self.validate_input(input_data)

            message = input_data.get("message", "")
            if not message:
                raise ValueError("message is required")

            # Try to find FAQ match
            faq_result = self._search_faq(message)

            if faq_result:
                response = self.create_response(
                    content=faq_result["answer"],
                    metadata={
                        "source": "faq",
                        "faq_type": faq_result["type"],
                        "matched_question": faq_result["question"],
                    },
                    confidence=0.95,
                )
            else:
                # Fall back to LLM for general inquiry
                response = await self._process_with_llm(message)

            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"General agent error: {e}")
            error_response = self.create_response(
                content=(
                    "I'm not sure how to answer that. "
                    "Please contact our support team at support@bank.com "
                    "or call 0800-123-4567."
                ),
                metadata={"error": str(e)},
                confidence=0.0,
            )
            return error_response

    # ========================================================================
    # FAQ PROCESSING
    # ========================================================================

    def _search_faq(self, query: str) -> Optional[Dict[str, str]]:
        """
        Search FAQ database for matching question.

        Args:
            query: Customer query

        Returns:
            dict or None: Matching FAQ or None
        """
        query_lower = query.lower()

        # Search by keywords
        for faq_type, faq_data in self.FAQ_DATABASE.items():
            question_lower = faq_data["question"].lower()

            # Exact match
            if query_lower == question_lower:
                return {
                    "type": faq_type,
                    "question": faq_data["question"],
                    "answer": faq_data["answer"],
                }

            # Keyword match (at least 2 matching words)
            query_words = set(query_lower.split())
            question_words = set(question_lower.split())
            matches = query_words & question_words

            if len(matches) >= 2:
                return {
                    "type": faq_type,
                    "question": faq_data["question"],
                    "answer": faq_data["answer"],
                }

        return None

    async def _process_with_llm(self, message: str) -> AgentResponse:
        """
        Process general query using LLM.

        Args:
            message: Customer message

        Returns:
            AgentResponse: Answer
        """
        # Build FAQ context
        faq_context = self._build_faq_context()

        prompt = (
            f"Customer Question: {message}\n\n"
            f"Available FAQ Information:\n{faq_context}\n\n"
            f"Answer the customer's question helpfully and accurately. "
            f"If you don't know the answer, direct them to contact support."
        )

        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful bank support agent. "
                        "Answer general questions about banking services accurately. "
                        "Be friendly and informative."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=self.config.max_tokens,
        )

        content = response.choices[0].message.content

        return self.create_response(
            content=content,
            metadata={
                "source": "llm",
                "faq_context": len(self.FAQ_DATABASE),
            },
            confidence=0.85,
        )

    def _build_faq_context(self) -> str:
        """Build FAQ context for LLM prompt."""
        context = ""
        for faq_type, faq_data in self.FAQ_DATABASE.items():
            context += f"Q: {faq_data['question']}\nA: {faq_data['answer']}\n\n"
        return context

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_faq_topics(self) -> List[str]:
        """Get list of FAQ topics."""
        return list(self.FAQ_DATABASE.keys())

    def get_faq_by_topic(self, topic: str) -> Optional[Dict[str, str]]:
        """Get FAQ by topic."""
        return self.FAQ_DATABASE.get(topic)
