"""
Admin Routes

Protected endpoints for administrative tasks including database seeding.
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import  Dict, Any, List
from app.api.routes.messages import coordinator
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# ============================================================================
# MODELS
# ============================================================================

class SeedRequest(BaseModel):
    """Request to seed database."""
    clear_first: bool = False
    customer_count: int = 100  # Allow custom customer count


class SeedResponse(BaseModel):
    """Response from seeding."""
    status: str
    message: str

# Add Model for Intervention/Approval
class InterventionRequest(BaseModel):
    """
    Request to approve/modify a paused agent action.
    """
    conversation_id: int
    approved_response: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/seed-db", response_model=SeedResponse)
async def seed_database(request: SeedRequest, background_tasks: BackgroundTasks):
    """
    Seed database with realistic sample data (1000+ records).

    WARNING: If clear_first=true, all existing data will be deleted!

    Args:
        request: Seed request with options
        background_tasks: FastAPI background tasks

    Returns:
        SeedResponse: Status of seeding operation

    Example:
        POST /api/v1/admin/seed-db
        {
            "clear_first": false,
            "customer_count": 100
        }
    """
    try:
        # Import here to avoid circular imports
        from app.seed_database import seed_all

        # Validate customer count
        customer_count = request.customer_count
        if customer_count < 10 or customer_count > 10000:
            raise ValueError("customer_count must be between 10 and 10000")

        # Run seeding in background
        background_tasks.add_task(
            seed_all,
            clear_first=request.clear_first,
            customer_count=customer_count
        )

        action = "Clearing database and seeding" if request.clear_first else "Seeding"

        return SeedResponse(
            status="started",
            message=f"{action} started with {customer_count} customers. "
                    f"This will generate ~{customer_count * 40:,} total records. Check logs for progress."
        )

    except Exception as e:
        logger.error(f"Failed to start seeding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start seeding: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "message": "Admin API is operational"
    }

#  Add Endpoint to Approve & Resume
@router.post("/interventions/approve")
async def approve_intervention(request: InterventionRequest):
    """
    Approve a paused conversation.

    1. Updates the state with the 'approved_response'.
    2. Sets 'is_compliant' to True.
    3. Resumes the LangGraph workflow from the paused node.
    """
    try:
        # Call the coordinator method we added in the previous step
        result = await coordinator.approve_intervention(
            conversation_id=request.conversation_id,
            new_response=request.approved_response
        )

        return {
            "status": "resumed",
            "message": "Workflow resumed successfully",
            "final_response": result
        }
    except Exception as e:
        logger.error(f"Failed to approve intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# [CHANGE 1d] Add Endpoint to List Pending (Mock/Placeholder)
@router.get("/interventions/pending")
async def get_pending_interventions():
    """
    Get list of conversations currently paused for human review.

    (Note: With MemorySaver, we cannot easily query 'all paused threads'
    without maintaining a separate index in DB. For MVP, we return a
    static message or you could implement a DB query for 'paused' status.)
    """
    # In a real production app using PostgresSaver, you would query the checkpoints table.
    return {
        "message": "To view pending interventions, check conversations with status='paused' in the database.",
        "count": "Unknown (Requires DB persistence layer for checkpoints)"
    }
