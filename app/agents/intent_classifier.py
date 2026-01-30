"""
Intent Classifier Agent

Classifies customer intent from messages to route to appropriate specialists.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from langfuse import observe
from langfuse import get_client

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ProductService




class IntentClassifierAgent(BaseAgent):
    """
    Intent classifier agent.

    Analyzes customer messages to determine intent and route appropriately.
    """

    # ========================================================================
    # INTENT CATEGORIES
    # ========================================================================

    INTENTS = {
        "loan_inquiry": {
            "description": "Customer asking about loans (mortgage, personal, business)",
            "examples": [
                "I want to apply for a mortgage",
                "What are your loan interest rates?",
                "Can I get a personal loan?",
            ],
            "routing": "product_recommender",
        },
        "account_inquiry": {
            "description": "Questions about EXISTING account details (balance, transactions, statements)",
            "examples": [
                "What is my account balance?",
                "Show me my recent transactions",
                "I need a bank statement",
                "What's my transaction history?",
                "How much can I spend?",
            ],
            "routing": "account_agent",
        },
        "credit_card": {
            "description": "Credit card related queries",
            "examples": [
                "I want to apply for a credit card",
                "What credit cards do you offer?",
                "Increase my credit limit",
            ],
            "routing": "product_recommender",
        },
        "complaint": {
            "description": "Customer complaints or issues",
            "examples": [
                "I'm not happy with the service",
                "This is taking too long",
                "I want to make a complaint",
                "I'm unhappy with your service",
                "I'm disappointed",
                "My card was stolen!",
                "I need immediate help!",
                "This is urgent!",
                "Emergency! My card is missing!"
            ],
            "routing": "human_agent",
        },
        "general_inquiry": {
            "description": "General questions, FAQs, how-to questions, or help/support contact requests",
            "examples": [
                "How do I open an account?",
                "How do I contact support?",
                "What services do you offer?",
                "How can I create a new account?",
                "How do I get help?",
                "What are your support hours?",
                "How do I reach customer service?",
            ],
            "routing": "general_agent",
        },
    }

    def __init__(self, config: Optional[AgentConfig] = None,
                 product_service: ProductService = None,
    **kwargs):
        """Initialize intent classifier agent."""
        super().__init__(name="intent_classifier", config=config)

        # Initialize Groq client
        self.client = AsyncGroq(api_key=self.config.api_key)
        self.product_service = product_service or ProductService()


    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        """Get agent description."""
        return (
            "Intent Classifier Agent - Analyzes customer messages to determine "
            "intent and route to appropriate specialist agents."
        )

    def _get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        return [
            "Intent classification",
            "Sentiment analysis",
            "Confidence scoring",
            "Multi-language support",
            "Context-aware classification",
        ]

    # ========================================================================
    # CORE PROCESSING
    # ========================================================================
    @observe(name="IntentClassifier")
    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Classify intent from customer message.

        Args:
            input_data: Must contain 'message' key
            context: Optional conversation context

        Returns:
            AgentResponse: Classification result
        """
        # Validate input
        await self.validate_input(input_data)

        # Log request
        self.log_request(input_data)

        # Extract message
        message = input_data.get("message", "")
        if not message:
            raise ValueError("Message is required")

        # Classify intent
        classification = await self._classify_intent(message, context)

        # Create response
        response = self.create_response(
            content=classification["intent"],
            metadata={
                "intent": classification["intent"],
                "sentiment": classification["sentiment"],
                "routing": classification["routing"],
                "explanation": classification["explanation"],
            },
            confidence=classification["confidence"],
        )

        # Log response
        self.log_response(response)

        return response

    # ========================================================================
    # CLASSIFICATION LOGIC
    # ========================================================================
    # Decorate the classification logic as a generation
    @observe(as_type="generation", name="Groq-Intent-Classification")
    async def _classify_intent(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Classify intent using LLM.

        Args:
            message: Customer message
            context: Optional context

        Returns:
            dict: Classification result
        """
        # Initialize Langfuse client for updates
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": self.config.temperature}
        )
        # Build prompt
        prompt = self._build_classification_prompt(message, context)
        try:



            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

            # Execute with stability logic
            response = await self.execute_with_retry(_call_llm)

            # Update Usage
            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )


            # Parse response
            result = self._parse_llm_response(response.choices[0].message.content)

            return result
        except Exception as e:
            raise e

    def _build_classification_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        # Intent descriptions
        intent_descriptions = "\n".join([
            f"- {intent}: {data['description']}"
            for intent, data in self.INTENTS.items()
        ])

        prompt = f"""Classify the customer message into one of these intents:

{intent_descriptions}

"""
        # [NEW] Inject History
        if context and "conversation_history" in context:
            history_list = context["conversation_history"]
            if history_list:
                history_str = "\n".join([
                    f"{msg['role'].upper()}: {msg['content']}"
                    for msg in history_list
                ])
                prompt += f"PREVIOUS CONVERSATION:\n{history_str}\n\n"

        prompt += f"""CURRENT CUSTOMER MESSAGE: "{message}"

Respond in this exact format:
INTENT: <intent_name>
CONFIDENCE: <0.0-1.0>
SENTIMENT: <positive|neutral|negative>
EXPLANATION: <brief explanation>
"""
        return prompt
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for LLM.

        Returns:
            str: System prompt
        """
        return """You are an expert intent classifier for a UK financial services company (FCA regulated).

Your job is to analyze customer messages and determine their intent accurately.

Guidelines:
- Be precise and confident in your classifications
- Consider context from conversation history
- Detect sentiment (positive, neutral, negative)
- Provide clear explanations
- Use the exact format requested"""

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured format.

        Args:
            response_text: Raw LLM response

        Returns:
            dict: Parsed classification
        """
        # Extract fields
        intent = "general_inquiry"  # Default
        confidence = 0.5
        sentiment = "neutral"
        explanation = ""

        for line in response_text.strip().split("\n"):
            line = line.strip()

            if line.startswith("INTENT:"):
                intent = line.split(":", 1)[1].strip().lower()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except:
                    confidence = 0.5
            elif line.startswith("SENTIMENT:"):
                sentiment = line.split(":", 1)[1].strip().lower()
            elif line.startswith("EXPLANATION:"):
                explanation = line.split(":", 1)[1].strip()

        # Get routing
        routing = self.INTENTS.get(intent, {}).get("routing", "general_agent")

        return {
            "intent": intent,
            "confidence": confidence,
            "sentiment": sentiment,
            "explanation": explanation,
            "routing": routing,
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_supported_intents(self) -> List[str]:
        """
        Get list of supported intents.

        Returns:
            List[str]: Intent names
        """
        return list(self.INTENTS.keys())

    def get_intent_info(self, intent: str) -> Optional[Dict[str, Any]]:
        """
        Get information about specific intent.

        Args:
            intent: Intent name

        Returns:
            dict or None: Intent information
        """
        return self.INTENTS.get(intent)
