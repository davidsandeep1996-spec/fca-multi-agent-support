"""
Message Router API

FastAPI endpoints for agent message processing.
Handles customer messages and returns coordinated responses.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from app.coordinator.agent_coordinator import AgentCoordinator

router = APIRouter(prefix="/api/v1", tags=["messages"])
coordinator = AgentCoordinator()
logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MessageRequest(BaseModel):
    """Incoming message request."""
    message: str
    customer_id: int
    conversation_id: int


class AgentMetadata(BaseModel):
    """Agent response metadata."""
    agent: str
    intent: str
    confidence: float
    turn_count: int
    escalated: bool
    escalation_id: Optional[str] = None


class MessageResponse(BaseModel):
    """API response."""
    response: str
    metadata: Dict[str, Any]
    status: str = "success"


class ConversationHistoryItem(BaseModel):
    """Single conversation turn."""
    timestamp: str
    message: str
    agent: str
    intent: str
    response: str


class ConversationHistory(BaseModel):
    """Conversation history response."""
    conversation_id: int
    history: list[ConversationHistoryItem]


class ConversationStats(BaseModel):
    """Conversation statistics."""
    total_conversations: int
    total_messages: int
    escalated_conversations: int
    avg_messages_per_conversation: float
    agent_distribution: Dict[str, int]
    intent_distribution: Dict[str, int]


# ============================================================================
# MESSAGE ENDPOINTS
# ============================================================================

@router.post("/messages/process", response_model=MessageResponse)
async def process_message(request: MessageRequest) -> MessageResponse:
    """
    Process customer message through agent system.

    Args:
        request: MessageRequest with message, customer_id, conversation_id

    Returns:
        MessageResponse with agent response and metadata

    Example:
        POST /api/v1/messages/process
        {
            "message": "What's my account balance?",
            "customer_id": 101,
            "conversation_id": 1
        }
    """
    try:
        logger.info(f"Processing message for customer {request.customer_id}")

        # Process through coordinator
        response = await coordinator.process_message(
            message=request.message,
            customer_id=request.customer_id,
            conversation_id=request.conversation_id,
        )

        return MessageResponse(
            response=response["response"],
            metadata={
                "agent": response["agent"],
                "intent": response["intent"],
                "confidence": response["confidence"],
                "turn_count": response["turn_count"],
                "escalated": response["escalated"],
                "escalation_id": response.get("escalation_id"),
            }
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Error processing message")


# ============================================================================
# CONVERSATION ENDPOINTS
# ============================================================================

@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistory)
async def get_conversation_history(
    conversation_id: int,
    limit: int = 10,
) -> ConversationHistory:
    """
    Get conversation history.

    Args:
        conversation_id: ID of conversation
        limit: Max messages to return

    Returns:
        ConversationHistory with message turns
    """
    try:
        history = coordinator.get_conversation_history(conversation_id, limit)

        if history is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistory(
            conversation_id=conversation_id,
            history=history,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"History retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving history")


@router.get("/customers/{customer_id}/conversations")
async def get_customer_conversations(customer_id: int) -> Dict[str, Any]:
    """
    Get all conversations for a customer.

    Args:
        customer_id: Customer ID

    Returns:
        List of conversations with metadata
    """
    try:
        conversations = coordinator.get_all_conversations(customer_id)

        return {
            "customer_id": customer_id,
            "conversations": [
                {
                    "conversation_id": conv.conversation_id,
                    "message_count": len(conv.messages),
                    "created_at": conv.created_at.isoformat(),
                    "is_escalated": conv.is_escalated,
                    "escalation_id": conv.escalation_id,
                    "last_intent": conv.last_intent,
                }
                for conv in conversations
            ]
        }

    except Exception as e:
        logger.error(f"Error retrieving conversations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving conversations")


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================

@router.get("/escalations")
async def get_escalated_conversations() -> Dict[str, Any]:
    """
    Get all escalated conversations.

    Returns:
        List of escalated conversations with details
    """
    try:
        escalated = coordinator.get_escalated_conversations()

        return {
            "escalated_count": len(escalated),
            "escalations": escalated,
        }

    except Exception as e:
        logger.error(f"Error retrieving escalations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving escalations")


@router.post("/escalations/{conversation_id}/resolve")
async def resolve_escalation(
    conversation_id: int,
    resolution_notes: str,
) -> Dict[str, Any]:
    """
    Mark escalation as resolved.

    Args:
        conversation_id: Conversation ID
        resolution_notes: Resolution details

    Returns:
        Success confirmation
    """
    try:
        resolved = coordinator.resolve_escalation(conversation_id, resolution_notes)

        if not resolved:
            raise HTTPException(status_code=404, detail="Conversation not escalated")

        return {
            "status": "resolved",
            "conversation_id": conversation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving escalation: {e}")
        raise HTTPException(status_code=500, detail="Error resolving escalation")


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@router.get("/statistics", response_model=ConversationStats)
async def get_statistics() -> ConversationStats:
    """
    Get coordinator statistics.

    Returns:
        ConversationStats with metrics
    """
    try:
        stats = coordinator.get_statistics()

        return ConversationStats(**stats)

    except Exception as e:
        logger.error(f"Error retrieving statistics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")


@router.get("/info")
async def get_coordinator_info() -> Dict[str, Any]:
    """
    Get coordinator information.

    Returns:
        Coordinator capabilities and status
    """
    try:
        info = coordinator.get_coordinator_info()
        return info

    except Exception as e:
        logger.error(f"Error retrieving info: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving info")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Status confirmation
    """
    return {
        "status": "healthy",
        "service": "message-router",
        "version": "1.0.0",
    }
