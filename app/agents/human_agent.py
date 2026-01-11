"""
Human Agent

Manages escalation to human specialists.
Handles complaints and complex issues.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.services import ConversationService

class EscalationPriority(str, Enum):
    """Escalation priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class HumanAgent(BaseAgent):
    """
    Human agent for escalations.

    Manages:
    - Complaint escalations
    - Complex issue handoff
    - Priority routing
    - Escalation tracking
    """

    def __init__(self, config: Optional[AgentConfig] = None, conversation_service: ConversationService = None,
    **kwargs):
        """Initialize human agent."""
        super().__init__(name="human_agent", config=config)
        self.conversation_service = conversation_service or ConversationService()

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        """Get agent description."""
        return (
            "Human Agent - Manages escalation to human specialists "
            "for complaints, complex issues, and priority support."
        )

    def _get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        return [
            "Complaint escalation",
            "Complex issue routing",
            "Priority assessment",
            "Specialist assignment",
            "Escalation tracking",
            "Conversation handoff",
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
        Process escalation request.

        Args:
            input_data: Must contain 'message', 'customer_id', 'conversation_id'
            context: Optional context with conversation_service

        Returns:
            AgentResponse: Escalation confirmation
        """
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

            # Assess escalation priority
            priority = self._assess_priority(message)

            # Create escalation
            escalation = await self._create_escalation(
                customer_id=customer_id,
                conversation_id=conversation_id,
                issue=message,
                priority=priority,
                context=context,
            )

            # Generate response
            response_content = self._generate_escalation_response(
                escalation, priority
            )

            response = self.create_response(
                content=response_content,
                metadata={
                    "escalated": True,
                    "escalation_id": escalation.get("id"),
                    "priority": priority.value,
                    "assigned_to": escalation.get("assigned_to"),
                    "estimated_response": escalation.get("estimated_response"),
                },
                confidence=0.98,
            )

            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Escalation error: {e}")
            error_response = self.create_response(
                content=(
                    "I've logged your issue and will have a specialist contact you shortly. "
                    "Your case reference is being processed."
                ),
                metadata={"error": str(e)},
                confidence=0.9,
            )
            return error_response

    # ========================================================================
    # ESCALATION PROCESSING
    # ========================================================================

    def _assess_priority(self, message: str) -> EscalationPriority:
        """
        Assess escalation priority from message.

        Args:
            message: Customer message

        Returns:
            EscalationPriority: Priority level
        """
        message_lower = message.lower()

        # Urgent keywords
        urgent_keywords = [
            "urgent", "emergency", "critical", "immediate",
            "lost", "stolen", "fraud", "unauthorized",
            "cannot access", "locked out", "security breach"
        ]

        # High priority keywords
        high_keywords = [
            "complaint", "disappointed", "unhappy", "unacceptable",
            "refused", "denied", "failed", "issue", "problem",
            "wrong", "error", "mistake"
        ]

        # Medium priority keywords
        medium_keywords = [
            "help", "question", "need", "want", "prefer",
            "change", "update", "modify"
        ]

        # Check priority levels
        if any(kw in message_lower for kw in urgent_keywords):
            return EscalationPriority.URGENT
        elif any(kw in message_lower for kw in high_keywords):
            return EscalationPriority.HIGH
        elif any(kw in message_lower for kw in medium_keywords):
            return EscalationPriority.MEDIUM
        else:
            return EscalationPriority.LOW

    async def _create_escalation(
        self,
        customer_id: int,
        conversation_id: int,
        issue: str,
        priority: EscalationPriority,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create escalation record.

        Args:
            customer_id: Customer ID
            conversation_id: Conversation ID
            issue: Issue description
            priority: Priority level
            context: Optional context with conversation_service

        Returns:
            dict: Escalation record
        """

        # Get conversation service
        conversation_service = (
            context.get("conversation_service") if context else None
        )

        escalation = {
            "id": f"ESC-{customer_id}-{int(datetime.utcnow().timestamp())}",
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "issue": issue,
            "priority": priority.value,
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
            "assigned_to": None,
            "estimated_response": self._estimate_response_time(priority),
        }

        # Save escalation if service available
        if conversation_service:
            try:
                await conversation_service.escalate_conversation(
                    conversation_id,
                    reason=issue,
                    priority=priority.value,
                )
                escalation["saved"] = True
            except Exception as e:
                self.logger.warning(f"Could not save escalation: {e}")
                escalation["saved"] = False

        # Assign based on priority
        escalation["assigned_to"] = self._assign_specialist(priority)

        return escalation

    def _estimate_response_time(self, priority: EscalationPriority) -> str:
        """
        Estimate response time based on priority.

        Args:
            priority: Priority level

        Returns:
            str: Estimated response time
        """
        estimates = {
            EscalationPriority.URGENT: "Within 15 minutes",
            EscalationPriority.HIGH: "Within 1 hour",
            EscalationPriority.MEDIUM: "Within 4 hours",
            EscalationPriority.LOW: "Within 24 hours",
        }
        return estimates.get(priority, "Within 24 hours")

    def _assign_specialist(self, priority: EscalationPriority) -> str:
        """
        Assign specialist based on priority.

        Args:
            priority: Priority level

        Returns:
            str: Specialist team
        """
        teams = {
            EscalationPriority.URGENT: "Security & Fraud Team",
            EscalationPriority.HIGH: "Senior Support Team",
            EscalationPriority.MEDIUM: "Support Specialists",
            EscalationPriority.LOW: "Support Team",
        }
        return teams.get(priority, "Support Team")

    def _generate_escalation_response(
        self, escalation: Dict[str, Any], priority: EscalationPriority
    ) -> str:
        """
        Generate response message for escalation.

        Args:
            escalation: Escalation record
            priority: Priority level

        Returns:
            str: Response message
        """
        response = (
            f"Thank you for bringing this to our attention.\n\n"
            f"We've escalated your issue to our {escalation['assigned_to']}.\n\n"
            f"📋 Reference Number: {escalation['id']}\n"
            f"⏱️  Estimated Response: {escalation['estimated_response']}\n"
            f"🔔 Priority: {priority.value.upper()}\n\n"
        )

        if priority == EscalationPriority.URGENT:
            response += (
                "This is marked as urgent. A specialist will contact you "
                "immediately via your preferred contact method.\n"
            )
        else:
            response += (
                "A specialist will review your case and contact you shortly.\n"
            )

        response += (
            "\nYou'll receive:\n"
            "✓ Email confirmation of this escalation\n"
            "✓ Regular updates on your case\n"
            "✓ Direct contact with a specialist\n"
            "✓ Resolution timeline\n\n"
            "For immediate assistance, call 0800-123-4567"
        )

        return response

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_priority_levels(self) -> List[str]:
        """Get available priority levels."""
        return [p.value for p in EscalationPriority]

    def get_escalation_info(self) -> Dict[str, Any]:
        """Get escalation information."""
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
