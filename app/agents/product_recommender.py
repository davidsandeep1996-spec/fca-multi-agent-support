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


import json
from pydantic import BaseModel, Field, field_validator

# [ENTERPRISE PATTERN 1] Define Strict Schemas for LLM Outputs


class ProductCategoryExtraction(BaseModel):
    """Schema for extracting the database category from natural language."""

    category: str = Field(
        description="Must be exactly one of: 'loan', 'credit', 'savings', 'current'",
        pattern="^(loan|credit|savings|current)$",
    )


class RecommendationResult(BaseModel):
    """Schema for the final product recommendation response."""

    recommended_product_names: List[str] = Field(
        description='A strict JSON array of exact product names. Example: ["Product A", "Product B"]. DO NOT use a comma-separated string.'
    )
    reasoning: str = Field(
        description="Why these products are suitable (output as a single string)"
    )
    key_benefits: str = Field(
        description="Main benefits of the products (output as a single string)"
    )
    next_steps: str = Field(
        description="Actionable next steps (output as a single string)"
    )
    is_direct_answer: bool = Field(
        description="True if answering a specific question about a product, False if making a general recommendation"
    )
    direct_answer_text: Optional[str] = Field(
        description="The answer text if is_direct_answer is True"
    )

    #  Validator for the lists
    @field_validator("recommended_product_names", mode="before")
    def correct_llm_string_to_list(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    #  Validator for the strings (catches plural hallucination)
    @field_validator("key_benefits", "next_steps", "reasoning", mode="before")
    def coerce_list_to_string(cls, v):
        if isinstance(v, list):
            # If LLM sends a list, join it automatically with bullet points
            return "\n".join(f"• {str(item)}" for item in v)
        return str(v)


class ProductRecommenderAgent(BaseAgent):
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        product_service: ProductService = None,
        **kwargs,
    ):
        super().__init__(name="product_recommender", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        self.product_service = product_service

    def _clean_json(self, raw_str: str) -> dict:
        """Safely extract and parse JSON even if the LLM wraps it in markdown backticks."""
        cleaned = raw_str.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return json.loads(cleaned.strip())

    def _get_schema_str(self, model_class: Any) -> str:
        """Safely gets the JSON schema regardless of Pydantic v1 or v2."""
        try:
            return json.dumps(model_class.model_json_schema(), indent=2)
        except AttributeError:
            return json.dumps(model_class.schema(), indent=2)  # Pydantic v1 fallback

    @observe(name="ProductRecommender")
    async def process(
        self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        await self.validate_input(input_data)
        self.log_request(input_data)

        intent = input_data.get("intent", "")
        message = input_data.get("message", "").lower()

        customer_profile = context.get("customer", {}) if context else {}

        history = context.get("conversation_history", []) if context else []

        try:
            async with self.product_service as service:
                recommendations = await self._generate_recommendations(
                    service, intent, message, customer_profile, history
                )

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
                confidence=0.0,
            )

    #  Decorate this helper as a 'generation' to capture LLM inputs/outputs
    @observe(as_type="generation", name="Groq-Product-Recs")
    async def _generate_recommendations(
        self,
        service: ProductService,
        intent: str,
        message: str,
        customer_profile: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # 1. Update trace with model params
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": 0.5, "max_tokens": self.config.max_tokens},
        )
        # 1. Map intent to DB type (loan, credit, savings, current)
        category = await self._determine_category(intent, message)

        # 2. Fetch from DB
        available_products = await service.get_products_by_category(category)

        if not available_products:
            return {
                "response_text": f"I currently don't have any specific {category} products to recommend.",
                "products": [],
                "reasoning": "No products found in database.",
                "disclaimers": [],
                "confidence": 0.5,
            }

        # 3. Build Prompt & Call LLM
        prompt = self._build_recommendation_prompt(
            intent, message, customer_profile, available_products, history
        )
        # schema_str = self._get_schema_str(RecommendationResult)
        sys_prompt = (
            self._get_system_prompt()
            + """

            You MUST output a SINGLE valid JSON object.
            Do NOT wrap it in an array. Do NOT output the schema definition.

            Your output MUST match this exact format:
            {
              "recommended_product_names": ["Product A", "Product B"],
              "reasoning": "Explanation here",
              "key_benefits": "Benefit 1\\nBenefit 2",
              "next_steps": "Step 1\\nStep 2",
              "is_direct_answer": false,
              "direct_answer_text": null
            }
            """
        )
        # ADDED: Manually track generation

        try:
            # WRAP LLM CALL
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"},
                )

            response = await self.execute_with_retry(_call_llm)

            # [ENTERPRISE PATTERN 3] Instant Pydantic Validation
            raw_json = json.loads(response.choices[0].message.content)
            # Unwrap the object if the LLM hallucinated an array
            if isinstance(raw_json, list) and len(raw_json) > 0:
                self.logger.warning(
                    "🛡️ Defense in Depth triggered: LLM returned an array instead of an object. Unwrapping..."
                )
                raw_json = raw_json[0]

            parsed_result = RecommendationResult.model_validate(raw_json)

            # Route logic based on structured data
            if parsed_result.is_direct_answer:
                return {
                    "response_text": parsed_result.direct_answer_text,
                    "products": [],
                    "reasoning": "Direct Q&A",
                    "disclaimers": [],
                    "confidence": 1.0,
                }

            # Map the exact string names back to DB objects safely
            matched_products = [
                p
                for p in available_products
                if p.name in parsed_result.recommended_product_names
            ]

            final_text = self._format_recommendation_text(
                matched_products,
                parsed_result.reasoning,
                parsed_result.key_benefits,
                parsed_result.next_steps,
            )

            #  Update usage stats on the active generation
            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            )

            return {
                "response_text": final_text,
                "products": matched_products,
                "reasoning": parsed_result.reasoning,
                "disclaimers": [],  # Compliance agent handles this now!
                "confidence": 0.8,
            }

        except Exception as e:
            raise e

    async def _determine_category(self, intent: str, message: str) -> str:
        """
         Semantic Category Extraction.
        Maps natural language ("buy a house") to a strict DB category using JSON mode.
        """
        if intent != "product_acquisition":
            return "savings"  # Fallback

        try:
            schema_str = self._get_schema_str(ProductCategoryExtraction)

            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": f"You map user requests to database categories. Output ONLY valid JSON strictly matching this schema:\n{schema_str}",
                    },
                    {"role": "user", "content": f"User said: '{message}'"},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            # Parse and validate with Pydantic
            raw_json = json.loads(response.choices[0].message.content)
            extracted = ProductCategoryExtraction.model_validate(raw_json)

            self.logger.info(
                f"🧠 Semantic mapping: '{message}' -> '{extracted.category}'"
            )
            return extracted.category

        except Exception as e:
            self.logger.warning(
                f"Semantic extraction failed, defaulting to savings: {e}"
            )
            return "savings"

    def _build_recommendation_prompt(
        self,
        intent: str,
        message: str,
        customer_profile: Dict[str, Any],
        available_products: List[Any],
        history: List[Dict[str, Any]],
    ) -> str:

        # Format history string
        history_str = ""
        if history:
            history_str = "RECENT CONVERSATION:\n" + "\n".join(
                [
                    f"- {msg.get('role', 'unknown')}: {msg.get('content', '')}"
                    for msg in history[-5:]
                ]
            )
        products_text = ""
        for i, p in enumerate(available_products, 1):
            features = ", ".join(p.features) if p.features else "Standard features"
            rate = f"{p.interest_rate}%" if p.interest_rate is not None else "Variable"

            # [FIX 1] Safely format the requirements dictionary into a readable string
            reqs = "None"
            if hasattr(p, "requirements") and p.requirements:
                reqs = ", ".join([f"{k}: {v}" for k, v in p.requirements.items()])

            products_text += (
                f"Product: {p.name}\n"
                f"Description: {p.description}\n"
                f"Interest Rate: {rate}\n"
                f"Features: {features}\n"
                f"Requirements: {reqs}\n\n"  # [FIX 2] Inject it into the LLM's view
            )
            products_text += f"{i}. Product: {p.name}...\n"

        is_vip = customer_profile.get("is_vip", False) if customer_profile else False
        customer_text = (
            f"\n\nCustomer Profile:\n- VIP Status: {'Yes' if is_vip else 'No'}"
        )

        return f"""You are a financial product expert.
        Based on the customer's needs, recommend the most suitable financial products.
RECENT CONVERSATION:
        {history_str}
Customer Intent: {intent}
CURRENT REQUEST: "{message}"{customer_text}

Available Products (from Database):
{products_text}

TASK:
0. IF the user is asking a specific question about a product...

   - [CRITICAL] ELIGIBILITY CHECK: Always check the "Requirements" field. If the user states their income, age, or deposit, and it does not meet the requirement, you MUST tell them they are not eligible.
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
        return """You are a Financial Product Recommender for a UK bank.
        You must recommend suitable products based on user needs, OR answer direct questions about specific products using ONLY the provided database information.

        CRITICAL FCA COMPLIANCE RULES:
        1. NEVER use the words: "guaranteed", "risk-free", "promise", "100% safe", or "can't lose".
        2. If the database features contain these prohibited words, you MUST rephrase them (e.g., change "Guaranteed return" to "Fixed return for the term").
        3. Be objective and balanced. Do not oversell.
        4. FINANCIAL MECHANICS: You are authorized to explain how products work.
            - For TRACKER MORTGAGES: You must explain that they move in line with the Bank of England base rate.
            - If the base rate decreases, the customer's interest rate and monthly payments will decrease.
        5. LIMITATIONS: Do not provide personal financial advice, but ALWAYS explain the underlying logic of the product mechanics.
        6. ACCURACY: Use the provided context to ensure terms are correct.

        NEVER recommend a specific product as the "best" or "right" choice for a user's personal circumstances.
        If a user asks for advice (e.g., "Which should I choose?", "What is best for me?"), you MUST:
        1. Provide objective facts about the options.
        2. Explicitly state: "I cannot provide financial advice."
        3. Advise them to consult an independent financial adviser.

        ANSWERING DIRECT QUESTIONS:
        - If the user asks a specific question about a product (like early withdrawal penalties), set "is_direct_answer" to true.
        - Answer using ONLY the provided product description and features.
        - If the exact penalty or rule is not in the database (e.g., it just says "Funds locked for term"), tell the user that funds are locked, but you do not have the exact penalty amounts and they should check the full terms and conditions. DO NOT hallucinate numbers.
        """

    def _format_recommendation_text(
        self, products, reasoning, key_benefits, next_steps
    ):
        text = "Based on your needs, I recommend:\n\n"
        for i, p in enumerate(products, 1):
            rate = f"{p.interest_rate}%" if p.interest_rate is not None else "Variable"
            text += f"{i}. **{p.name}**\n   {p.description}\n   Rate: {rate}\n\n"
        if reasoning:
            text += f"**Why?**\n{reasoning}\n\n"
        if key_benefits:
            text += f"**Benefits:**\n{key_benefits}\n\n"
        if next_steps:
            text += f"**Next Steps:**\n{next_steps}\n\n"
        return text

    def _get_description(self) -> str:
        return "Product Recommender - Recommends financial products from the database."

    def _get_capabilities(self) -> List[str]:
        return ["Product recommendation", "Needs analysis"]
