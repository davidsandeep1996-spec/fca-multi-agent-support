"""
Agent Coordinator

Manages conversation state, routing, and persistence.
Coordinates multi-agent responses across conversation turns.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.workflows.message_workflow import MessageWorkflow


class ConversationMessage:
    """Single message in conversation."""

    def __init__(
        self,
        customer_id: int,
        message: str,
        agent_type: str,
        response: str,
        intent: str,
        confidence: float,
    ):
        self.timestamp = datetime.utcnow()
        self.customer_id = customer_id
        self.message = message
        self.agent_type = agent_type
        self.response = response
        self.intent = intent
        self.confidence = confidence


class ConversationContext:
    """Maintains conversation state and history."""

    def __init__(self, customer_id: int, conversation_id: int):
        self.customer_id = customer_id
        self.conversation_id = conversation_id
        self.messages: List[ConversationMessage] = []
        self.created_at = datetime.utcnow()
        self.last_intent = None
        self.escalation_id = None
        self.is_escalated = False

    def add_message(
        self,
        message: str,
        agent_type: str,
        response: str,
        intent: str,
        confidence: float,
    ) -> None:
        """Add message to conversation history."""
        conv_msg = ConversationMessage(
            customer_id=self.customer_id,
            message=message,
            agent_type=agent_type,
            response=response,
            intent=intent,
            confidence=confidence,
        )
        self.messages.append(conv_msg)
        self.last_intent = intent

    def mark_escalated(self, escalation_id: str) -> None:
        """Mark conversation as escalated."""
        self.is_escalated = True
        self.escalation_id = escalation_id

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history."""
        recent = self.messages[-limit:]
        return [
            {
                "timestamp": msg.timestamp.isoformat(),
                "message": msg.message,
                "agent": msg.agent_type,
                "intent": msg.intent,
                "response": msg.response[:100] + "...",
            }
            for msg in recent
        ]


class AgentCoordinator:
    """
    Coordinates multi-agent responses.

    Manages:
    - Conversation state
    - Message routing
    - Escalations
    - Persistence
    """

    def __init__(self):
        """Initialize coordinator."""
        self.logger = logging.getLogger(__name__)
        self.workflow = MessageWorkflow()
        self.conversations: Dict[int, ConversationContext] = {}

    # ========================================================================
    # CONVERSATION MANAGEMENT
    # ========================================================================

    def get_or_create_conversation(
        self,
        customer_id: int,
        conversation_id: int,
    ) -> ConversationContext:
        """Get or create conversation context."""

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext(
                customer_id=customer_id,
                conversation_id=conversation_id,
            )

        return self.conversations[conversation_id]

    async def process_message(
        self,
        message: str,
        customer_id: int,
        conversation_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process message through workflow and persist.

        Args:
            message: Customer message
            customer_id: Customer ID
            conversation_id: Conversation ID
            context: Optional context

        Returns:
            dict: Coordinated response
        """
        self.logger.info(f"\n🔄 Coordinating message for customer {customer_id}")

        # Get or create conversation
        conv_context = self.get_or_create_conversation(customer_id, conversation_id)

        # Route through workflow
        workflow_response = await self.workflow.process_message(
            message=message,
            customer_id=customer_id,
            conversation_id=conversation_id,
            context=context,
        )

        # Extract response data
        agent_type = workflow_response.get("agent")
        response_text = workflow_response.get("message")
        intent = workflow_response.get("intent")
        confidence = workflow_response.get("confidence", 0.0)

        # Add to conversation history
        conv_context.add_message(
            message=message,
            agent_type=agent_type,
            response=response_text,
            intent=intent,
            confidence=confidence,
        )

        # Check for escalation
        escalation_id = workflow_response.get("metadata", {}).get("escalation_id")
        if escalation_id:
            conv_context.mark_escalated(escalation_id)
            self.logger.info(f"⚠️ Escalation detected: {escalation_id}")

        # Build coordinated response
        coordinated_response = {
            "response": response_text,
            "agent": agent_type,
            "intent": intent,
            "confidence": confidence,
            "conversation_id": conversation_id,
            "turn_count": len(conv_context.messages),
            "escalated": conv_context.is_escalated,
            "escalation_id": escalation_id,
        }

        self.logger.info(f"✅ Message processed: {agent_type} agent, turn #{len(conv_context.messages)}")

        return coordinated_response

    # ========================================================================
    # PERSISTENCE & RETRIEVAL
    # ========================================================================

    def get_conversation(self, conversation_id: int) -> Optional[ConversationContext]:
        """Get conversation by ID."""
        return self.conversations.get(conversation_id)

    def get_conversation_history(
        self,
        conversation_id: int,
        limit: int = 10,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get conversation history."""
        conv = self.get_conversation(conversation_id)
        if conv:
            return conv.get_history(limit)
        return None

    def get_all_conversations(self, customer_id: int) -> List[ConversationContext]:
        """Get all conversations for a customer."""
        return [
            conv for conv in self.conversations.values()
            if conv.customer_id == customer_id
        ]

    # ========================================================================
    # ESCALATION MANAGEMENT
    # ========================================================================

    def get_escalated_conversations(self) -> List[Dict[str, Any]]:
        """Get all escalated conversations."""
        escalated = []
        for conv in self.conversations.values():
            if conv.is_escalated:
                escalated.append({
                    "conversation_id": conv.conversation_id,
                    "customer_id": conv.customer_id,
                    "escalation_id": conv.escalation_id,
                    "message_count": len(conv.messages),
                    "created_at": conv.created_at.isoformat(),
                })
        return escalated

    def resolve_escalation(
        self,
        conversation_id: int,
        resolution_notes: str,
    ) -> bool:
        """Mark escalation as resolved."""
        conv = self.get_conversation(conversation_id)
        if conv and conv.is_escalated:
            self.logger.info(f"✅ Escalation resolved: {conv.escalation_id}")
            return True
        return False

    # ========================================================================
    # STATISTICS & MONITORING
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get coordination statistics."""
        total_messages = sum(
            len(conv.messages) for conv in self.conversations.values()
        )
        escalated_count = sum(
            1 for conv in self.conversations.values()
            if conv.is_escalated
        )

        # Agent distribution
        agent_counts = {}
        for conv in self.conversations.values():
            for msg in conv.messages:
                agent = msg.agent_type
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Intent distribution
        intent_counts = {}
        for conv in self.conversations.values():
            for msg in conv.messages:
                intent = msg.intent
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

        return {
            "total_conversations": len(self.conversations),
            "total_messages": total_messages,
            "escalated_conversations": escalated_count,
            "agent_distribution": agent_counts,
            "intent_distribution": intent_counts,
            "avg_messages_per_conversation": (
                total_messages / len(self.conversations)
                if self.conversations else 0
            ),
        }

    def get_coordinator_info(self) -> Dict[str, Any]:
        """Get coordinator information."""
        return {
            "type": "AgentCoordinator",
            "workflow": "LangGraph (MessageWorkflow)",
            "agents": 6,
            "conversation_memory": len(self.conversations),
            "features": [
                "Multi-turn conversations",
                "Intent tracking",
                "Escalation management",
                "Conversation history",
                "Statistics & monitoring",
            ],
        }
