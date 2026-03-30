"""
Human Agent (Enterprise Grade)

Manages intelligent escalation to human specialists.
Handles complaints and complex issues with Semantic Priority Assessment.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from groq import AsyncGroq

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ConversationService
from langfuse import observe, get_client

# ============================================================================
# ENTERPRISE SCHEMAS
# ============================================================================


class EscalationPriority(str, Enum):
    """Escalation priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# RESTORED: Your original exact Pydantic Model
class EscalationTicket(BaseModel):
    id: str
    customer_id: int
    conversation_id: int
    issue: str
    priority: str
    status: str = "open"
    assigned_to: str
    estimated_response: str
    saved: bool
    created_at: str


class PriorityAnalysis(BaseModel):
    """Strict schema for LLM Priority Assessment."""

    priority: EscalationPriority = Field(
        description="The semantic priority level of the customer's issue."
    )
    reasoning: str = Field(
        description="A brief explanation of why this priority was chosen."
    )


# ============================================================================
# HUMAN ESCALATION AGENT
# ============================================================================


class HumanAgent(BaseAgent):
    """
    Human agent for escalations.
    Manages semantic priority routing and tracked handoffs.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        conversation_service: ConversationService = None,
        **kwargs,
    ):
        super().__init__(name="human_agent", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)
        self.conversation_service = conversation_service or ConversationService()

    def _get_description(self) -> str:
        return "Human Agent - Manages intelligent escalation to human specialists for complaints and complex issues."

    def _get_capabilities(self) -> List[str]:
        return [
            "Semantic priority assessment",
            "Complaint escalation",
            "Specialist assignment",
            "Escalation tracking",
        ]

    @observe(name="HumanAgent")
    async def process(
        self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        self.log_request(input_data)

        try:
            await self.validate_input(input_data)

            message = input_data.get("message", "")
            customer_id = input_data.get("customer_id")
            conversation_id = input_data.get("conversation_id")

            if not all([message, customer_id, conversation_id]):
                raise ValueError(
                    "message, customer_id, and conversation_id are required"
                )

            # 1. Semantic Priority Assessment (Upgraded to AI)
            priority = await self._assess_priority(message)

            # 2. Create escalation ticket
            escalation = await self._create_escalation(
                customer_id=customer_id,
                conversation_id=conversation_id,
                issue=message,
                priority=priority,
                context=context,
            )

            # 3. Generate structured response
            response_content = self._generate_escalation_response(escalation, priority)

            response = self.create_response(
                content=response_content,
                metadata={
                    "escalated": True,
                    "escalation_id": escalation.id,
                    "priority": priority.value,
                    "assigned_to": escalation.assigned_to,
                    "estimated_response": escalation.estimated_response,
                    "saved": escalation.saved,  # RESTORED: Matches your original variable exactly
                },
                confidence=0.98,
            )
            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Escalation error: {e}")
            # ENTERPRISE FIX: If DB fails, tell the user to call so no ticket is lost silently!
            return self.create_response(
                content=(
                    "⚠️ We experienced a technical issue logging your request. "
                    "For immediate assistance, please call our 24/7 support line at 0800-123-4567."
                ),
                metadata={"error": str(e), "escalated": False},
                confidence=0.0,
            )

    @observe(as_type="generation", name="Groq-Priority-Assessment")
    async def _assess_priority(self, message: str) -> EscalationPriority:
        """Deep semantic priority assessment using Hybrid Logic & LLM."""

        # 1. Hybrid Fast-Path: Catch blatant emergencies instantly to save LLM latency
        message_lower = message.lower()
        if any(
            kw in message_lower
            for kw in ["fraud", "stolen", "unauthorized", "security breach"]
        ):
            if "not " not in message_lower and "no " not in message_lower:
                return EscalationPriority.URGENT

        # 2. LLM Semantic Assessment
        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name, model_parameters={"temperature": 0.0}
        )

        # ENTERPRISE FIX: Provide a concrete Zero-Shot Example instead of a raw JSON Schema
        prompt = f"""
        Analyze the following customer message to determine its escalation priority.

        Customer Message: "{message}"

        Priority Levels:
        - URGENT: Fraud, stolen cards, security breaches, locked out of accounts.
        - HIGH: Formal complaints, unacceptable service, denied transactions, system errors.
        - MEDIUM: Standard support requests, account changes, document requests.
        - LOW: General inquiries, non-urgent questions.

        You MUST respond with a single valid JSON object. Do NOT wrap it in a list or array.
        It must contain exactly these keys: "priority" (string: "low", "medium", "high", or "urgent") and "reasoning" (string).

        Example Output:
        {{
            "priority": "medium",
            "reasoning": "The customer is asking for help with a standard account update."
        }}
        """

        try:

            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a senior customer support triage expert.",
                        },
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

            analysis = PriorityAnalysis.model_validate_json(
                response.choices[0].message.content
            )
            return analysis.priority

        except Exception as e:
            self.logger.error(f"LLM Priority Parsing Error: {e}")
            # Safe fallback: Default to HIGH to ensure human attention quickly if AI API fails
            return EscalationPriority.HIGH

    async def _create_escalation(
        self,
        customer_id: int,
        conversation_id: int,
        issue: str,
        priority: EscalationPriority,
        context: Optional[Dict[str, Any]] = None,
    ) -> EscalationTicket:
        """Create escalation record with STRICT DB validation."""

        # RESTORED: Explicit service fetching
        conversation_service = None
        if context:
            conversation_service = context.get("conversation_service")
        if not conversation_service:
            conversation_service = self.conversation_service

        ticket_id = f"ESC-{customer_id}-{int(datetime.utcnow().timestamp())}"
        assigned_group = self._assign_specialist(priority)
        saved_status = False

        if conversation_service:
            try:
                # ENTERPRISE FIX: Throw hard error if DB is disconnected, never swallow it!
                if (
                    hasattr(conversation_service, "db")
                    and conversation_service.db is not None
                ):
                    await conversation_service.escalate_conversation(
                        conversation_id,
                        reason=issue,
                        priority=priority.value,
                        assigned_group=assigned_group,
                        ticket_id=ticket_id,
                    )
                    saved_status = True
                    self.logger.info(
                        f"Escalation saved to DB for conversation {conversation_id}"
                    )
                else:
                    raise ConnectionError(
                        "Database connection is null in ConversationService"
                    )
            except Exception as e:
                self.logger.error(f"CRITICAL: Failed to save escalation to DB: {e}")
                raise e

        return EscalationTicket(
            id=ticket_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            issue=issue,
            priority=priority.value,
            status="open",
            created_at=datetime.utcnow().isoformat(),
            assigned_to=assigned_group,
            estimated_response=self._estimate_response_time(priority),
            saved=saved_status,
        )

    def _estimate_response_time(self, priority: EscalationPriority) -> str:
        estimates = {
            EscalationPriority.URGENT: "Within 15 minutes",
            EscalationPriority.HIGH: "Within 1 hour",
            EscalationPriority.MEDIUM: "Within 4 hours",
            EscalationPriority.LOW: "Within 24 hours",
        }
        return estimates.get(priority, "Within 24 hours")

    def _assign_specialist(self, priority: EscalationPriority) -> str:
        teams = {
            EscalationPriority.URGENT: "Security & Fraud Team",
            EscalationPriority.HIGH: "Senior Support Team",
            EscalationPriority.MEDIUM: "Support Specialists",
            EscalationPriority.LOW: "Support Team",
        }
        return teams.get(priority, "Support Team")

    def _generate_escalation_response(
        self, escalation: EscalationTicket, priority: EscalationPriority
    ) -> str:
        response = (
            f"Thank you for bringing this to our attention.\n\n"
            f"We've escalated your issue to our {escalation.assigned_to}.\n\n"
            f"📋 Reference Number: {escalation.id}\n"
            f"⏱️  Estimated Response: {escalation.estimated_response}\n"
            f"🔔 Priority: {priority.value.upper()}\n\n"
        )

        if priority == EscalationPriority.URGENT:
            response += "This is marked as urgent. A specialist will contact you immediately via your preferred contact method.\n"
        else:
            response += "A specialist will review your case and contact you shortly.\n"

        response += (
            "\nYou'll receive:\n"
            "✓ Email confirmation of this escalation\n"
            "✓ Regular updates on your case\n"
            "✓ Direct contact with a specialist\n"
            "✓ Resolution timeline\n\n"
            "For immediate assistance, call 0800-123-4567"
        )
        return response

    def get_priority_levels(self) -> List[str]:
        return [p.value for p in EscalationPriority]

    def get_escalation_info(self) -> Dict[str, Any]:
        return {
            "priorities": self.get_priority_levels(),
            "specialist_teams": [
                "Security & Fraud Team",
                "Senior Support Team",
                "Support Specialists",
                "Support Team",
            ],
            "response_targets": {
                "urgent": "15 minutes",
                "high": "1 hour",
                "medium": "4 hours",
                "low": "24 hours",
            },
        }
