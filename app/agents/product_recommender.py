"""
Product Recommender Agent

Recommends financial products based on customer needs and profile.
FCA compliant recommendations with clear explanations.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq

from app.agents.base import BaseAgent, AgentConfig, AgentResponse


class ProductRecommenderAgent(BaseAgent):
    """
    Product recommender agent.

    Analyzes customer needs and recommends suitable financial products.
    """

    # ========================================================================
    # PRODUCT CATALOG
    # ========================================================================

    PRODUCTS = {
        "mortgages": {
            "fixed_rate_mortgage": {
                "name": "Fixed Rate Mortgage",
                "description": "Interest rate stays the same for agreed period",
                "rates": "From 3.99% APR",
                "terms": "2, 3, 5, or 10 year fixed terms",
                "suitable_for": ["First time buyers", "Remortgaging", "Stability seekers"],
                "min_deposit": "5%",
            },
            "tracker_mortgage": {
                "name": "Tracker Mortgage",
                "description": "Interest rate tracks Bank of England base rate",
                "rates": "Base rate + 1.5%",
                "terms": "Flexible terms",
                "suitable_for": ["Rate optimists", "Flexible borrowers"],
                "min_deposit": "10%",
            },
        },
        "savings": {
            "instant_access_saver": {
                "name": "Instant Access Savings",
                "description": "Access your money anytime without penalties",
                "rates": "Up to 4.25% AER",
                "terms": "No fixed term",
                "suitable_for": ["Emergency funds", "Short-term goals"],
                "min_balance": "£1",
            },
            "fixed_rate_bond": {
                "name": "Fixed Rate Bond",
                "description": "Fixed interest rate for set period",
                "rates": "Up to 5.10% AER",
                "terms": "1, 2, 3, or 5 years",
                "suitable_for": ["Long-term savings", "Higher returns"],
                "min_balance": "£1,000",
            },
        },
        "credit_cards": {
            "cashback_card": {
                "name": "Cashback Credit Card",
                "description": "Earn cashback on purchases",
                "rates": "Up to 1% cashback",
                "terms": "Representative 21.9% APR",
                "suitable_for": ["Regular spenders", "Paying full balance monthly"],
                "annual_fee": "£0",
            },
            "balance_transfer_card": {
                "name": "Balance Transfer Card",
                "description": "0% interest on transferred balances",
                "rates": "0% for 24 months",
                "terms": "3% transfer fee",
                "suitable_for": ["Debt consolidation", "Interest savings"],
                "annual_fee": "£0",
            },
        },
        "loans": {
            "personal_loan": {
                "name": "Personal Loan",
                "description": "Unsecured loan for any purpose",
                "rates": "From 6.9% APR",
                "terms": "1-7 years",
                "suitable_for": ["Home improvements", "Debt consolidation", "Major purchases"],
                "amount_range": "£1,000 - £35,000",
            },
        },
    }

    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize product recommender agent."""
        super().__init__(name="product_recommender", config=config)

        # Initialize Groq client
        self.client = AsyncGroq(api_key=self.config.api_key)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        """Get agent description."""
        return (
            "Product Recommender Agent - Analyzes customer needs and recommends "
            "suitable financial products with FCA-compliant explanations."
        )

    def _get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        return [
            "Product recommendation",
            "Needs analysis",
            "Personalization based on customer profile",
            "FCA compliance",
            "Clear product comparisons",
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
        Recommend products based on customer needs.

        Args:
            input_data: Must contain 'intent' or 'message'
            context: Optional customer context (profile, history)

        Returns:
            AgentResponse: Product recommendations
        """
        # Validate input
        await self.validate_input(input_data)

        # Log request
        self.log_request(input_data)

        # Extract intent and message
        intent = input_data.get("intent", "")
        message = input_data.get("message", "")

        # Get customer context
        customer_profile = context.get("customer", {}) if context else {}

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            intent=intent,
            message=message,
            customer_profile=customer_profile,
        )

        # Create response
        response = self.create_response(
            content=recommendations["response_text"],
            metadata={
                "products": recommendations["products"],
                "reasoning": recommendations["reasoning"],
                "disclaimers": recommendations["disclaimers"],
            },
            confidence=recommendations["confidence"],
        )

        # Log response
        self.log_response(response)

        return response

    # ========================================================================
    # RECOMMENDATION LOGIC
    # ========================================================================

    async def _generate_recommendations(
        self,
        intent: str,
        message: str,
        customer_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate product recommendations using LLM.

        Args:
            intent: Customer intent
            message: Customer message
            customer_profile: Customer information

        Returns:
            dict: Recommendations with reasoning
        """
        # Determine product category
        category = self._determine_category(intent)

        # Get available products
        available_products = self._get_products_for_category(category)

        # Build prompt
        prompt = self._build_recommendation_prompt(
            intent=intent,
            message=message,
            customer_profile=customer_profile,
            available_products=available_products,
        )

        # Call LLM
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.5,  # Lower for more consistent recommendations
            max_tokens=self.config.max_tokens,
        )

        # Parse response
        result = self._parse_recommendation_response(
            response.choices[0].message.content,
            available_products,
        )

        return result

    def _determine_category(self, intent: str) -> str:
        """
        Determine product category from intent.

        Args:
            intent: Customer intent

        Returns:
            str: Product category
        """
        intent_to_category = {
            "loan_inquiry": "mortgages",
            "mortgage_inquiry": "mortgages",
            "savings_inquiry": "savings",
            "credit_card": "credit_cards",
            "personal_loan": "loans",
        }

        return intent_to_category.get(intent, "mortgages")

    def _get_products_for_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get products for category.

        Args:
            category: Product category

        Returns:
            List[dict]: Available products
        """
        products = []
        category_products = self.PRODUCTS.get(category, {})

        for product_id, product_data in category_products.items():
            products.append({
                "id": product_id,
                **product_data,
            })

        return products

    def _build_recommendation_prompt(
        self,
        intent: str,
        message: str,
        customer_profile: Dict[str, Any],
        available_products: List[Dict[str, Any]],
    ) -> str:
        """
        Build prompt for recommendations.

        Args:
            intent: Customer intent
            message: Customer message
            customer_profile: Customer info
            available_products: Products to recommend from

        Returns:
            str: Formatted prompt
        """
        # Format products
        products_text = "\n\n".join([
            f"Product: {p['name']}\n"
            f"Description: {p['description']}\n"
            f"Rates: {p.get('rates', 'N/A')}\n"
            f"Terms: {p.get('terms', 'N/A')}\n"
            f"Suitable for: {', '.join(p.get('suitable_for', []))}"
            for p in available_products
        ])

        # Customer context
        customer_text = ""
        if customer_profile:
            is_vip = customer_profile.get("is_vip", False)
            customer_text = f"\n\nCustomer Profile:\n- VIP Status: {'Yes' if is_vip else 'No'}"

        prompt = f"""Based on the customer's needs, recommend the most suitable financial products.

Customer Intent: {intent}
Customer Message: "{message}"{customer_text}

Available Products:
{products_text}

Provide recommendations in this format:
RECOMMENDED PRODUCTS: <comma-separated product names>
REASONING: <why these products are suitable>
KEY BENEFITS: <main benefits for customer>
NEXT STEPS: <what customer should do>
CONFIDENCE: <0.0-1.0>

Guidelines:
- Recommend 1-3 most suitable products
- Explain clearly why each product fits their needs
- Be FCA compliant (clear, fair, not misleading)
- Include relevant disclaimers
- Consider customer profile (VIP gets premium options)
"""

        return prompt

    def _get_system_prompt(self) -> str:
        """
        Get system prompt for LLM.

        Returns:
            str: System prompt
        """
        return """You are a financial product recommendation specialist for a UK bank (FCA regulated).

Your role:
- Recommend suitable financial products based on customer needs
- Provide clear, fair, and not misleading information (FCA principles)
- Explain product features and benefits clearly
- Consider customer circumstances and profile
- Include appropriate disclaimers and warnings

FCA Compliance:
- Always be clear about rates, terms, and conditions
- Mention risks where relevant
- Don't promise guaranteed returns
- Be balanced in your recommendations
- Disclose representative APR where applicable

Remember: Customers must make informed decisions based on complete information."""

    def _parse_recommendation_response(
        self,
        response_text: str,
        available_products: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Parse LLM recommendation response.

        Args:
            response_text: Raw LLM response
            available_products: Available products

        Returns:
            dict: Parsed recommendations
        """
        # Extract fields
        recommended_products = []
        reasoning = ""
        key_benefits = ""
        next_steps = ""
        confidence = 0.8

        for line in response_text.strip().split("\n"):
            line = line.strip()

            if line.startswith("RECOMMENDED PRODUCTS:"):
                products_str = line.split(":", 1)[1].strip()
                recommended_products = [p.strip() for p in products_str.split(",")]
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("KEY BENEFITS:"):
                key_benefits = line.split(":", 1)[1].strip()
            elif line.startswith("NEXT STEPS:"):
                next_steps = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except:
                    confidence = 0.8

        # Get full product details
        products = []
        for product_name in recommended_products:
            for p in available_products:
                if product_name.lower() in p["name"].lower():
                    products.append(p)
                    break

        # Build response text
        response_text = self._format_recommendation_text(
            products=products,
            reasoning=reasoning,
            key_benefits=key_benefits,
            next_steps=next_steps,
        )

        # Standard disclaimers
        disclaimers = [
            "Products subject to eligibility and affordability assessment",
            "Rates and terms subject to change",
            "Representative APR quoted - your rate may differ",
            "FCA regulated - complaints can be referred to Financial Ombudsman",
        ]

        return {
            "response_text": response_text,
            "products": products,
            "reasoning": reasoning,
            "disclaimers": disclaimers,
            "confidence": confidence,
        }

    def _format_recommendation_text(
        self,
        products: List[Dict[str, Any]],
        reasoning: str,
        key_benefits: str,
        next_steps: str,
    ) -> str:
        """
        Format recommendation as customer-facing text.

        Args:
            products: Recommended products
            reasoning: Why recommended
            key_benefits: Main benefits
            next_steps: What to do next

        Returns:
            str: Formatted text
        """
        text = "Based on your needs, I recommend the following products:\n\n"

        # Products
        for i, product in enumerate(products, 1):
            text += f"{i}. **{product['name']}**\n"
            text += f"   {product['description']}\n"
            text += f"   Rates: {product.get('rates', 'Varies')}\n"
            text += f"   Terms: {product.get('terms', 'Standard terms apply')}\n\n"

        # Reasoning
        if reasoning:
            text += f"**Why these products?**\n{reasoning}\n\n"

        # Benefits
        if key_benefits:
            text += f"**Key Benefits:**\n{key_benefits}\n\n"

        # Next steps
        if next_steps:
            text += f"**Next Steps:**\n{next_steps}\n\n"

        # Disclaimer
        text += "\n*Products subject to eligibility assessment. Representative rates shown - your rate may differ.*"

        return text

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_product_categories(self) -> List[str]:
        """
        Get available product categories.

        Returns:
            List[str]: Category names
        """
        return list(self.PRODUCTS.keys())

    def get_products_in_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all products in category.

        Args:
            category: Product category

        Returns:
            List[dict]: Products
        """
        return self._get_products_for_category(category)
