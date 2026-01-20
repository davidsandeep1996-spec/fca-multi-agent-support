from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime



class AgentResponse(BaseModel):
    """Standard output for all agents."""
    content: str
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class WorkflowState(BaseModel):
    """The 'Memory' passed between LangGraph nodes."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Inputs
    message: str
    customer_id: int
    conversation_id: int = 0
    context: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    # Flow State
    intent: Optional[str] = None
    intent_confidence: float = 0.0

    # Agent Outputs
    agent_type: Optional[str] = None
    agent_response: Optional[str] = None
    agent_metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0

    # Compliance
    is_compliant: bool = True
    compliance_check: Optional[str] = None
    required_disclaimers: List[str] = Field(default_factory=list)

    # Final
    final_response: Optional[Dict[str, Any]] = None
