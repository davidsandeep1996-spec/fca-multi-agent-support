# app/agents/general_agent.py
"""
General Agent (Enterprise Grade)
Handles general inquiries, FAQ lookups, and Vector RAG over knowledge bases.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services.faq_service import FAQService
from app.services.rag_service import RAGService
from app.services.cache_service import CacheService

from langfuse import observe
from langfuse import get_client

class GeneralAgent(BaseAgent):
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        faq_service: FAQService = None,
        rag_service: RAGService = None,
        cache_service: CacheService = None,
        **kwargs,
    ):
        super().__init__(name="general_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        self.faq_service = faq_service
        self.rag_service = rag_service
        # Initialize Cache Service, failing safely if Redis is down
        self.cache_service = cache_service or CacheService()

    def _get_description(self) -> str:
        return "Handles general inquiries, FAQs, and knowledge base document retrieval."

    def _get_capabilities(self) -> List[str]:
        return ["FAQ lookup", "Document RAG retrieval", "Conversational memory", "Privacy-safe handling", "Semantic Caching"]

    @observe(name="GeneralAgent")
    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        await self.validate_input(input_data)
        self.log_request(input_data)

        message = input_data.get("message", "")
        # ENTERPRISE FIX: Safe list initialization to prevent cross-session memory leaks
        history = context.get("conversation_history", []) if context else []

        try:
            # =================================================================
            # 🚀 TIER 0: REDIS CACHE (0ms latency, 0 API cost)
            # =================================================================
            if self.cache_service:
                cached_answer = await self.cache_service.get_cached_response(message)
                if cached_answer:
                    return self.create_response(
                        content=cached_answer,
                        metadata={"source": "redis_cache"},
                        confidence=1.0,
                    )

            # =================================================================
            # 🗄️ TIER 1: PostgreSQL FAQ Lookup (Zero LLM Cost)
            # =================================================================
            faq_answer = await self._lookup_faq_db(message)
            if faq_answer:
                # Self-Warming Cache: Save DB result to Redis for the next user (24h TTL)
                if self.cache_service:
                    await self.cache_service.set_cached_response(message, faq_answer, ttl_seconds=86400)

                return self.create_response(
                    content=faq_answer,
                    metadata={"source": "faq_db"},
                    confidence=1.0,
                )

            # =================================================================
            # 🧠 TIER 2: Vector RAG Search + Groq LLM Generation
            # =================================================================
            rag_documents = await self._lookup_rag_db(message)
            response = await self._generate_llm_response(message, rag_documents, history)

            # Self-Warming Cache: Cache successful RAG queries (1h TTL) to avoid regenerating
            if rag_documents and response.confidence > 0.8 and self.cache_service:
                await self.cache_service.set_cached_response(message, response.content, ttl_seconds=3600)

            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"General Agent processing error: {e}")
            return self.create_response(
                content="I apologize, but I am having trouble connecting right now. Please try again later.",
                metadata={"error": "internal_system_error", "source": "error_fallback"},
                confidence=0.0,
            )

    async def _lookup_faq_db(self, query: str) -> Optional[str]:
        """Search DB for exact FAQ match."""
        if not self.faq_service:
            return None
        try:
            results = await self.faq_service.search_faqs(query)
            return results[0].answer if results else None
        except Exception as e:
            self.logger.error(f"FAQ Search failed: {e}")
            return None

    async def _lookup_rag_db(self, query: str) -> List[Dict[str, Any]]:
        """ENTERPRISE FIX: Returns structured document metadata instead of a flattened string."""
        if not self.rag_service:
            return []
        try:
            results = await self.rag_service.search(query, limit=6)
            return results if results else []
        except Exception as e:
            self.logger.error(f"RAG Search failed: {e}")
            return []

    @observe(as_type="generation", name="Groq-General-Chat")
    async def _generate_llm_response(
        self,
        message: str,
        rag_documents: List[Dict[str, Any]],
        history: List[Dict[str, str]]
    ) -> AgentResponse:

        langfuse = get_client()
        langfuse.update_current_generation(model=self.config.model_name, model_parameters={"temperature": 0.7})

        # 1. Format System Prompt Safely
        system_prompt = self._build_system_prompt()

        # 2. Build Context Injection
        user_prompt = self._build_user_prompt(message, rag_documents, history)

        try:
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                )

            response = await self.execute_with_retry(_call_llm)

            # ENTERPRISE FIX: Track exactly where the knowledge came from
            source = "rag_database" if rag_documents else "llm_fallback"
            citations = [doc.get("filename", "Unknown Document") for doc in rag_documents]

            if hasattr(response, 'usage') and response.usage:
                langfuse.update_current_generation(
                    usage_details={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                )

            return self.create_response(
                content=response.choices[0].message.content,
                metadata={
                    "source": source,
                    "citations": list(set(citations)) # Pass PDF filenames back to the frontend!
                },
                confidence=0.85 if rag_documents else 0.7,
            )

        except Exception as e:
            raise e # Caught safely in the outer process() method

    def _build_system_prompt(self) -> str:
        """Clean, deduped system instructions."""
        return """You are a helpful banking assistant.

CRITICAL RULES:
1. DATA PRIVACY: User input is sanitized. You will see tokens like [NAME], [EMAIL], or [PHONE].
   NEVER repeat these tokens as if they are real values.
   Instead, replace them with a generic phrase (e.g., 'I have noted your name safely.').
2. KNOWLEDGE RESTRICTION: If KNOWLEDGE BASE DOCUMENTS are provided, answer USING ONLY THOSE DOCUMENTS.
   If the answer is not in the documents, state that you do not have that specific policy information.
3. MEMORY: Use the provided CONVERSATION HISTORY to answer follow-up questions."""

    def _build_user_prompt(self, message: str, rag_documents: List[Dict[str, Any]], history: List[Dict[str, str]]) -> str:
        """Safely injects dynamic user state into the prompt without corrupting system instructions."""
        prompt_parts = []

        if history:
            history_str = "\n".join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in history[-5:]])
            prompt_parts.append(f"CONVERSATION HISTORY:\n{history_str}")

        if rag_documents:
            context_str = "\n".join([f"--- Source: {doc.get('filename', 'Unknown')} ---\n{doc.get('content', '')}" for doc in rag_documents])
            prompt_parts.append(f"KNOWLEDGE BASE DOCUMENTS:\n{context_str}")

        prompt_parts.append(f"CURRENT QUESTION:\n{message}")

        return "\n\n".join(prompt_parts)
