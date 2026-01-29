"""
General Agent (Refactored for DB)
"""
from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services.faq_service import FAQService

from langfuse import observe

from langfuse import get_client

class GeneralAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, faq_service: FAQService = None, **kwargs):
        super().__init__(name="general_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        # [CRITICAL] This must be here to use the DB
        self.faq_service = faq_service

    @observe(name="GeneralAgent")
    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        await self.validate_input(input_data)
        message = input_data.get("message", "")

        # 1. Try DB Lookup first
        faq_answer = await self._lookup_faq_db(message)

        if faq_answer:
            # [CRITICAL] This specific metadata tag matches the verify script
            return self.create_response(
                content=faq_answer,
                metadata={"source": "faq_db", "confidence": 1.0},
                confidence=1.0
            )

        return await self._generate_llm_response(message)

    @observe(as_type="generation", name="Groq-General-Chat")
    async def _generate_llm_response(self, message: str) -> AgentResponse:
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": 0.7}
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful banking assistant."},
                    {"role": "user", "content": message}
                ],
                temperature=0.7
            )

            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )

            return self.create_response(
                content=response.choices[0].message.content,
                metadata={"source": "llm_fallback"},
                confidence=0.7
            )
        except Exception as e:
            return self.create_response(
                content="I'm having trouble connecting right now.",
                metadata={"error": str(e)},
                confidence=0.0
            )

    async def _lookup_faq_db(self, query: str) -> Optional[str]:
        """Search DB for FAQ match."""
        if not self.faq_service:
            return None

        # Search the database
        results = await self.faq_service.search_faqs(query)

        if results:
            return results[0].answer
        return None

    def _get_description(self) -> str: return "Handles general inquiries."
    def _get_capabilities(self) -> List[str]: return ["FAQ lookup"]
