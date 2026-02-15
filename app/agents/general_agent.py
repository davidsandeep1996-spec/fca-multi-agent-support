"""
General Agent (Refactored for DB)
"""
from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services.faq_service import FAQService
from app.services.rag_service import RAGService

from langfuse import observe

from langfuse import get_client

class GeneralAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, faq_service: FAQService = None, rag_service: RAGService = None, **kwargs):
        super().__init__(name="general_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

        # [CRITICAL] This must be here to use the DB
        self.faq_service = faq_service
        self.rag_service = rag_service


    async def _lookup_rag_db(self, query: str) -> str:
        """Search Vector DB for relevant PDF document chunks."""
        if not self.rag_service:
            return ""

        try:
            results = await self.rag_service.search(query, limit=6)
            if not results:
                return ""

            # Format the chunks into a readable context block
            context = "KNOWLEDGE BASE DOCUMENTS:\n"
            for r in results:
                context += f"--- Source: {r['filename']} ---\n{r['content']}\n\n"
            return context
        except Exception as e:
            self.logger.error(f"RAG Search failed: {e}")
            return ""

    @observe(name="GeneralAgent")
    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        await self.validate_input(input_data)
        message = input_data.get("message", "")

        history = context.get("conversation_history", []) if context else []


        # 1. Try DB Lookup first
        faq_answer = await self._lookup_faq_db(message)

        if faq_answer:
            #  This specific metadata tag matches the verify script
            return self.create_response(
                content=faq_answer,
                metadata={"source": "faq_db", "confidence": 1.0},
                confidence=1.0
            )

        # 2. [NEW] Try Vector RAG Search for complex document queries
        rag_context = await self._lookup_rag_db(message)

        return await self._generate_llm_response(message, rag_context, history)

    @observe(as_type="generation", name="Groq-General-Chat")
    async def _generate_llm_response(self, message: str, rag_context: str = "", history: List[Dict[str, str]] = []) -> AgentResponse:
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": 0.7}
        )

        # 1. Format History for System Prompt
        history_str = ""
        if history:
            history_str = "CONVERSATION HISTORY:\n" + "\n".join(
                [f"{msg['role'].upper()}: {msg['content']}" for msg in history[-5:]]
            )


        prompt_message = message
        if rag_context:
            prompt_message = f"{rag_context}\n\nUSER QUESTION: {message}"
        try:
            # WRAP LLM CALL
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": ("You are a helpful banking assistant.\n"
                                                       "You may receive a 'CONVERSATION HISTORY' block before the user's message.\n"
                            "If the user asks 'What did I say?', refer to that history.\n"
                            "NOTE: User input may be sanitized for privacy. \n"
                            "If you see tokens like [NAME], [EMAIL], or [PHONE], do NOT repeat them as if they are real values.\n"
                            "Instead, acknowledge the information was received but protected (e.g., 'Nice to meet you, I've noted your details safely').\n"
                            "Do NOT invent information not in the history."
                            "PRIVACY RULE: User data is sanitized. You will see tokens like [NAME], [EMAIL].\n"
                            "When referring to them, ALWAYS replace the token with a generic phrase like 'your name' or 'the details you provided'.\n"
                            "EXAMPLE:\n"
                            "Bad: 'Your name is [NAME]'\n"
                            "Good: 'I see you provided your name.'\n"
                            "Use the CONVERSATION HISTORY to answer context questions."
                            "You may also receive a 'KNOWLEDGE BASE DOCUMENTS' block. If provided, answer the user's question USING ONLY THOSE DOCUMENTS. "
                            "If the answer is not in the documents, say you don't have that specific policy information.\n"
                             f"{history_str}\n\n" # History goes here
                            "Use the history above to answer questions like 'What did I just say?'.\n")
                        },
                        {"role": "user", "content": prompt_message}
                    ],
                    temperature=0.7
                )

            response = await self.execute_with_retry(_call_llm)

            # Check if we used RAG to update the metadata correctly
            source = "rag_database" if rag_context else "llm_fallback"

            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )

            return self.create_response(
                content=response.choices[0].message.content,
                metadata={"source": source},
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
