"""
Intent Classifier Agent (Enterprise Grade)

Classifies customer intent from messages to route to appropriate specialists.
Uses Google-style "Few-Shot" training phrases and Strict Pydantic JSON validation.
"""

import json
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from groq import AsyncGroq
from langfuse import observe, get_client

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ProductService

# ============================================================================
# ENTERPRISE SCHEMAS
# ============================================================================


class IntentClassification(BaseModel):
    """Strict schema for intent classification and routing."""

    intent: Literal[
        "product_acquisition",
        "account_data",
        "knowledge_inquiry",
        "complaint",
        "general_inquiry",
    ] = Field(description="The classified intent of the user's message.")

    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0."
    )

    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="The emotional sentiment of the message."
    )

    explanation: str = Field(
        description="A brief, 1-sentence explanation of why this intent was chosen."
    )


# ============================================================================
# INTENT CLASSIFIER AGENT
# ============================================================================


class IntentClassifierAgent(BaseAgent):
    """
    Intent classifier agent.
    Analyzes customer messages to determine intent and route appropriately.
    """

    # ========================================================================
    # INTENT CATEGORIES
    # ========================================================================

    INTENTS = {
        "product_acquisition": {
            "description": """Customer wants RECOMMENDATIONS, wants to APPLY, or is asking for DETAILS/OPTIONS/TERMS about a specific product (loans, bonds, cards, accounts, savings for a goal). \n
            CRITICAL RULE: You MUST choose this intent if the user mentions a SPECIFIC product by name (e.g., 'Fixed Rate Bond', 'Mortgage', 'Credit Card') and asks about its rules, penalties, early withdrawals, terms, or features. This handles both sales AND specific product policy questions.""",
            "examples": [
                "I want to apply for a mortgage",
                "What are your loan interest rates?",
                "What is the best account to put my emergency fund into?",
                "I am traveling next month and need a plastic card",
                "Tell me more about the Fixed Rate Bond",
                "Can I get a personal loan?",
                "Is the loan guaranteed?",
                "Tell me more about that product",
                "What are the terms for the first option?",
                "What are your rates for new customers?",
            ],
            "routing": "product_recommender",
        },
        "account_data": {
            "description": "Fetching SPECIFIC numerical data about the user's existing account (Balance, Transactions, Dates).",
            "examples": [
                "What is my account balance?",
                "Show me my recent transactions",
                "I need a bank statement",
                "What's my transaction history?",
                "How much can I spend?",
                "How much money do I have?",
            ],
            "routing": "account_agent",
        },
        "knowledge_inquiry": {
            "description": "Questions about POLICIES, RULES, FEES, LIMITS, PENALTIES or 'HOW TO'. General banking knowledge.",
            "examples": [
                "Can I overpay my mortgage?",
                "What is the fee for CHAPS?",
                "What happens if I withdraw my money early? Are there penalties?",
                "How do I close my account?",
                "Is Open Banking safe?",
                "What are the rules for overdrafts?",
                "What is the daily limit?",
                "How do I open an account?",
                "How do I contact support?",
                "What services do you offer?",
                "Can I withdraw cash using my credit card?",
                "How can I create a new account?",
                "How do I get help?",
                "What are your support hours?",
                "What is the daily limit?",
                "How do I reach customer service?",
            ],
            "routing": "general_agent",
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
                "Emergency! My card is missing!",
            ],
            "routing": "human_agent",
        },
        "general_inquiry": {
            "description": "Greetings, vague help requests, or conversation history checks.",
            "examples": [
                "Hello",
                "Hi",
                "Thank you",
                "Who are you?",
                "What did I just say?",
            ],
            "routing": "general_agent",
        },
    }

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        product_service: ProductService = None,
        **kwargs,
    ):
        super().__init__(name="intent_classifier", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)
        self.product_service = product_service or ProductService()

    def _get_description(self) -> str:
        return "Intent Classifier Agent - Analyzes customer messages to determine intent and route to appropriate specialist agents."

    def _get_capabilities(self) -> List[str]:
        return [
            "Intent classification",
            "Sentiment analysis",
            "Confidence scoring",
            "Multi-language support",
            "Context-aware classification",
        ]

    def _limit_history_context(
        self, context: Optional[Dict[str, Any]], max_turns: int = 2
    ) -> List[Dict[str, str]]:
        if context and "conversation_history" in context:
            history = context["conversation_history"]
            if history:
                return history[-max_turns:]
        return []

    @observe(name="IntentClassifier")
    async def process(
        self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        self.log_request(input_data)

        try:
            await self.validate_input(input_data)
            message = input_data.get("message", "")

            if not message:
                raise ValueError("Message is required")

            classification = await self._classify_intent(message, context)

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
            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Intent Classification error: {e}")
            # ENTERPRISE FIX: Safe Degradation. If the LLM fails, route to General Agent safely.
            return self.create_response(
                content="general_inquiry",
                metadata={
                    "intent": "general_inquiry",
                    "sentiment": "neutral",
                    "routing": "general_agent",
                    "explanation": "System fallback due to technical error.",
                    "error": str(e),
                },
                confidence=0.0,
            )

    @observe(as_type="generation", name="Groq-Intent-Classification")
    async def _classify_intent(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={
                "temperature": 0.0
            },  # Keep temp 0 for deterministic routing
        )

        prompt = self._build_classification_prompt(message, context)

        try:

            async def _call_llm():
                return await self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

            response = await self.execute_with_retry(_call_llm)

            if hasattr(response, "usage") and response.usage:
                langfuse.update_current_generation(
                    usage_details={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                )

            parsed_data = IntentClassification.model_validate_json(
                response.choices[0].message.content
            )
            routing = self.INTENTS.get(parsed_data.intent, {}).get(
                "routing", "general_agent"
            )

            return {
                "intent": parsed_data.intent,
                "confidence": parsed_data.confidence,
                "sentiment": parsed_data.sentiment,
                "explanation": parsed_data.explanation,
                "routing": routing,
            }

        except Exception as e:
            self.logger.error(f"LLM parsing failed: {e}")
            raise e

    def _build_classification_prompt(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        # ENTERPRISE FIX: Inject the Training Phrases (Examples) into the prompt like Dialogflow!
        intent_blocks = []
        for intent, data in self.INTENTS.items():
            # Pass up to 5 examples to the LLM to teach it the exact pattern
            examples_str = "\n    - ".join(data.get("examples", [])[:5])
            block = f"- **{intent}**\n  Description: {data['description']}\n  Examples:\n    - {examples_str}"
            intent_blocks.append(block)

        intent_descriptions = "\n\n".join(intent_blocks)
        schema_json = json.dumps(IntentClassification.model_json_schema(), indent=2)

        prompt = f"""Classify the customer message into one of these exact intents. Study the examples carefully:

{intent_descriptions}

"""
        recent_history = self._limit_history_context(context, max_turns=2)
        if recent_history:
            history_str = "\n".join(
                [
                    f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
                    for msg in recent_history
                ]
            )
            prompt += f"PREVIOUS CONVERSATION HISTORY:\n{history_str}\n\n"

        prompt += f"""CURRENT CUSTOMER MESSAGE: "{message}"

You MUST respond with a single valid JSON object exactly matching this schema:
{schema_json}

Example Output:
{{
    "intent": "account_data",
    "confidence": 0.95,
    "sentiment": "neutral",
    "explanation": "The user is asking for their specific account balance."
}}
"""
        return prompt

    def _get_system_prompt(self) -> str:
        return """You are an expert intent classifier for a UK financial services company.

Your job is to analyze customer messages and determine their intent accurately.

Guidelines:
- Consider context from conversation history.
- SPECIAL RULE: If a user asks about their *past* conversation (e.g., "What did I just say?"), classify as 'general_inquiry'.

CRITICAL ROUTING RULES:
1. **account_data**: ONLY select this if the user asks for *numbers* or *specific records* (Balance, Transactions).
   - "Can I overpay?" is NOT account_data (It is a Rule/Policy).
   - "What is my balance?" IS account_data.

2. **product_acquisition**: ONLY select this if the user wants to *buy/open* something NEW or asks about specific product rules.
   - "Is approval guaranteed for the personal loan?" -> product_acquisition
   - "What are the rules for mortgages?" is NOT acquisition (It is knowledge).
   - "I want a new mortgage" IS product_acquisition.

3. **knowledge_inquiry**: Select this for ANY question about how the bank works, rules, fees, penalties, or "Can I..." questions, EVEN IF they mention a specific product.
   - "What is the penalty for closing a Fixed Rate Bond early?" -> knowledge_inquiry (Because it requires reading the PDF terms and conditions).
   - "Can I overpay my mortgage?" -> knowledge_inquiry.
"""

    def get_supported_intents(self) -> List[str]:
        return list(self.INTENTS.keys())

    def get_intent_info(self, intent: str) -> Optional[Dict[str, Any]]:
        return self.INTENTS.get(intent)
