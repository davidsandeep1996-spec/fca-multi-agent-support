"""
Product Recommender Agent
Recommends financial products based on customer needs and profile.
"""
from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ProductService

class ProductRecommenderAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, product_service: ProductService = None, **kwargs):
        super().__init__(name="product_recommender", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)


        self.product_service = product_service

    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        await self.validate_input(input_data)
        self.log_request(input_data)

        intent = input_data.get("intent", "")
        message = input_data.get("message", "")
        customer_profile = context.get("customer", {}) if context else {}

        try:
            async with self.product_service as service:

                recommendations = await self._generate_recommendations(service,intent, message, customer_profile)

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

    async def _generate_recommendations(self, service: ProductService, intent: str, message: str, customer_profile: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Map intent to DB type (loan, credit, savings, current)
        category = self._determine_category(intent)

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
        prompt = self._build_recommendation_prompt(intent, message, customer_profile, available_products)
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=self.config.max_tokens,
        )

        return self._parse_recommendation_response(response.choices[0].message.content, available_products)

    def _determine_category(self, intent: str) -> str:
        # Maps Agent Intent -> DB 'type' column
        intent_to_db_type = {
            "loan_inquiry": "loan",
            "mortgage_inquiry": "loan",
            "personal_loan": "loan",
            "savings_inquiry": "savings",
            "credit_card": "credit",
            "account_opening": "current",
        }
        return intent_to_db_type.get(intent, "savings")

    def _build_recommendation_prompt(self, intent: str, message: str, customer_profile: Dict[str, Any], available_products: List[Any]) -> str:
        products_text = ""
        for p in available_products:
            features = ", ".join(p.features) if p.features else "Standard features"
            rate = f"{p.interest_rate}%" if p.interest_rate is not None else "Variable"
            products_text += (
                f"Product: {p.name}\n"
                f"Description: {p.description}\n"
                f"Interest Rate: {rate}\n"
                f"Features: {features}\n\n"
            )

        is_vip = customer_profile.get("is_vip", False) if customer_profile else False
        customer_text = f"\n\nCustomer Profile:\n- VIP Status: {'Yes' if is_vip else 'No'}"

        return f"""Based on the customer's needs, recommend the most suitable financial products.
Customer Intent: {intent}
Customer Message: "{message}"{customer_text}

Available Products (from Database):
{products_text}

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
