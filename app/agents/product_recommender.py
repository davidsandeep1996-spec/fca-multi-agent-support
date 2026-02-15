"""
Product Recommender Agent
Recommends financial products based on customer needs and profile.
"""
from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ProductService

from langfuse import observe
from langfuse import get_client

class ProductRecommenderAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, product_service: ProductService = None, **kwargs):
        super().__init__(name="product_recommender", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)


        self.product_service = product_service

    @observe(name="ProductRecommender")
    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        await self.validate_input(input_data)
        self.log_request(input_data)

        intent = input_data.get("intent", "")
        message = input_data.get("message", "").lower()
        # If user asks "Can I..." or "How to...", this is Support, not Sales.
        # Exception: "How to apply"
        support_triggers = ["can i", "rules", "penalty", "fee", "change", "cancel", "stop" ,"how do i", "is it possible", "what happens if",
            "withdraw", "limit", "fee", "charge", "penalty", "cancel", "lost", "stolen"]

        if any(t in message for t in support_triggers) and "apply" not in message:
             return self.create_response(
                content="I can help you apply for new products, but for questions about managing existing accounts or policies, please ask our Support team.",
                metadata={"routing_handoff": "general_agent"}, # Signal to coordinator if you want advanced routing
                confidence=0.0 # Return 0 confidence so logic falls back
             )
        customer_profile = context.get("customer", {}) if context else {}

        history = context.get("conversation_history", []) if context else []

        try:
            async with self.product_service as service:

                recommendations = await self._generate_recommendations(service,intent, message, customer_profile, history)

            response = self.create_response(
                content=recommendations["response_text"],
                metadata={
                    "products": [p.name for p in recommendations["products"]],
                    "reasoning": recommendations["reasoning"],
                    "disclaimers": recommendations["disclaimers"],
                },
                confidence=recommendations["confidence"],
            )
            self.log_response(response)
            return response
        except Exception as e:
            self.logger.error(f"Product recommendation error: {e}", exc_info=True)
            return self.create_response(
                content="I apologize, but I'm having trouble retrieving product information right now.",
                metadata={"error": str(e)},
                confidence=0.0
            )
    #  Decorate this helper as a 'generation' to capture LLM inputs/outputs
    @observe(as_type="generation", name="Groq-Product-Recs")
    async def _generate_recommendations(self, service: ProductService, intent: str, message: str, customer_profile: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 1. Update trace with model params
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": 0.5, "max_tokens": self.config.max_tokens}
        )
        # 1. Map intent to DB type (loan, credit, savings, current)
        category = self._determine_category(intent, message)

        # 2. Fetch from DB
        available_products = await service.get_products_by_category(category)

        if not available_products:
             return {
                 "response_text": f"I currently don't have any specific {category} products to recommend.",
                 "products": [],
                 "reasoning": "No products found in database.",
                 "disclaimers": [],
                 "confidence": 0.5
             }

        # 3. Build Prompt & Call LLM
        prompt = self._build_recommendation_prompt(intent, message, customer_profile, available_products, history)

        # ADDED: Manually track generation

        try:
            # WRAP LLM CALL
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                    max_tokens=self.config.max_tokens,
                )

            response = await self.execute_with_retry(_call_llm)

            #  Update usage stats on the active generation
            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )

            return self._parse_recommendation_response(response.choices[0].message.content, available_products)

        except Exception as e:
            raise e


    def _determine_category(self, intent: str, message: str) -> str:
        # Maps Agent Intent -> DB 'type' column


        # 1. Dynamic Parsing for "product_acquisition"
        if intent == "product_acquisition":
            msg_lower = message.lower()
            if "mortgage" in msg_lower or "loan" in msg_lower:
                return "loan"
            if "card" in msg_lower:
                return "credit"
            if "account" in msg_lower and "current" in msg_lower:
                return "current"
            # Default fallthrough to savings
        intent_to_db_type = {
            "loan_inquiry": "loan",
            "mortgage_inquiry": "loan",
            "personal_loan": "loan",
            "savings_inquiry": "savings",
            "credit_card": "credit",
            "account_opening": "current",
        }
        return intent_to_db_type.get(intent, "savings")

    def _build_recommendation_prompt(self, intent: str, message: str, customer_profile: Dict[str, Any], available_products: List[Any], history: List[Dict[str, Any]]) -> str:

        # Format history string
        history_str = ""
        if history:
             history_str = "RECENT CONVERSATION:\n" + "\n".join(
                [f"- {msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in history[-5:]]
             )
        products_text = ""
        for i, p in enumerate(available_products, 1):
            features = ", ".join(p.features) if p.features else "Standard features"
            rate = f"{p.interest_rate}%" if p.interest_rate is not None else "Variable"
            products_text += (
                f"Product: {p.name}\n"
                f"Description: {p.description}\n"
                f"Interest Rate: {rate}\n"
                f"Features: {features}\n\n"
            )
            products_text += f"{i}. Product: {p.name}...\n"

        is_vip = customer_profile.get("is_vip", False) if customer_profile else False
        customer_text = f"\n\nCustomer Profile:\n- VIP Status: {'Yes' if is_vip else 'No'}"

        return f"""You are a financial product expert.
        Based on the customer's needs, recommend the most suitable financial products.
RECENT CONVERSATION:
        {history_str}
Customer Intent: {intent}
CURRENT REQUEST: "{message}"{customer_text}

Available Products (from Database):
{products_text}

TASK:
1. IF the user is asking a specific question about a product (e.g., "Is it guaranteed?", "Tell me more about the first one", "What are the rates?"):
   - Identify the specific product they are referring to from the History or the Message.
   - Answer their question DIRECTLY using the product details.
   - Do NOT just list the products again.
   - [CRITICAL] COMPLIANCE RULE: If the user asks if a loan is "Guaranteed", you MUST say "No loan is guaranteed. Approval is subject to status and credit checks." You can mention the *rate* is fixed, but never imply approval is guaranteed.
   - FORMAT: "ANSWER: <Your detailed answer>"

2. IF the user is asking for suggestions (e.g., "I need a loan", "What do you have?"):
   - Recommend the best matching products from the list above.
   - FORMAT:
     RECOMMENDED PRODUCTS: <names>
     REASONING: <why>
     KEY BENEFITS: <bullets>
     NEXT STEPS: <action>

IMPORTANT: If the user asks about a specific product mentioned previously (e.g., "the second one", "the tracker"), use the History and the Numbered List above to identify it.

Provide recommendations in this format:
RECOMMENDED PRODUCTS: <comma-separated product names>
REASONING: <why suitable>
KEY BENEFITS: <main benefits>
NEXT STEPS: <action items>
CONFIDENCE: <0.0-1.0>
"""

    def _get_system_prompt(self) -> str:
        return "You are a financial product recommendation specialist for a UK bank (FCA regulated). Recommend suitable products, explain benefits clearly, and include risks."

    def _parse_recommendation_response(self, response_text: str, available_products: List[Any]) -> Dict[str, Any]:


        if "ANSWER:" in response_text:
            answer_text = response_text.split("ANSWER:", 1)[1].strip()
            return {
                "response_text": answer_text,
                "products": [], # No specific list needed for Q&A
                "reasoning": "Direct Q&A",
                "disclaimers": [], # Compliance checker will add them if needed
                "confidence": 1.0
            }

        recommended_names = []
        reasoning = ""
        key_benefits = ""
        next_steps = ""
        confidence = 0.8

        for line in response_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("RECOMMENDED PRODUCTS:"):
                products_str = line.split(":", 1)[1].strip()
                recommended_names = [p.strip() for p in products_str.split(",")]
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("KEY BENEFITS:"):
                key_benefits = line.split(":", 1)[1].strip()
            elif line.startswith("NEXT STEPS:"):
                next_steps = line.split(":", 1)[1].strip()

        matched_products = []
        for name in recommended_names:
            for p in available_products:
                if name.lower() in p.name.lower():
                    matched_products.append(p)
                    break

        final_text = self._format_recommendation_text(matched_products, reasoning, key_benefits, next_steps)

        return {
            "response_text": final_text,
            "products": matched_products,
            "reasoning": reasoning,
            "disclaimers": ["Representative APR quoted - your rate may differ", "Subject to status"],
            "confidence": confidence,
        }

    def _format_recommendation_text(self, products, reasoning, key_benefits, next_steps):
        text = "Based on your needs, I recommend:\n\n"
        for i, p in enumerate(products, 1):
            rate = f"{p.interest_rate}%" if p.interest_rate is not None else "Variable"
            text += f"{i}. **{p.name}**\n   {p.description}\n   Rate: {rate}\n\n"
        if reasoning: text += f"**Why?**\n{reasoning}\n\n"
        if key_benefits: text += f"**Benefits:**\n{key_benefits}\n\n"
        if next_steps: text += f"**Next Steps:**\n{next_steps}\n\n"
        return text

    def _get_description(self) -> str:
        return "Product Recommender - Recommends financial products from the database."

    def _get_capabilities(self) -> List[str]:
        return ["Product recommendation", "Needs analysis"]
