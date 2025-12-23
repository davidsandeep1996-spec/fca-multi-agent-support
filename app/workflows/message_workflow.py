"""
Message Workflow

Multi-agent orchestration using LangGraph.
Routes messages through Intent Classifier → Specialized Agents.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import logging

from langgraph.graph import StateGraph, END

from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.account_agent import AccountAgent
from app.agents.general_agent import GeneralAgent
from app.agents.human_agent import HumanAgent
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.compliance_checker import ComplianceCheckerAgent


class WorkflowState(str, Enum):
    """Workflow states."""
    START = "start"
    CLASSIFY = "classify"
    ACCOUNT = "account"
    GENERAL = "general"
    PRODUCT = "product"
    COMPLIANCE = "compliance"
    HUMAN = "human"
    END = "end"


class MessageWorkflow:
    """
    Multi-agent message workflow.

    Flow:
    1. Intent Classifier → determines intent
    2. Conditional routing:
       - account_inquiry → Account Agent
       - general_inquiry → General Agent
       - product_inquiry → Product Agent → Compliance Check
       - complaint → Human Agent (escalation)
    3. Response formatting
    """

    def __init__(self):
        """Initialize workflow with all agents."""
        self.logger = logging.getLogger(__name__)

        # Initialize all agents
        self.intent_classifier = IntentClassifierAgent()
        self.account_agent = AccountAgent()
        self.general_agent = GeneralAgent()
        self.product_agent = ProductRecommenderAgent()
        self.compliance_agent = ComplianceCheckerAgent()
        self.human_agent = HumanAgent()

        # Build LangGraph workflow
        self.graph = self._build_graph()
        self.workflow = self.graph.compile()

    def _build_graph(self):
        """Build LangGraph state machine."""

        # Create state graph
        workflow = StateGraph(dict)

        # Define nodes
        workflow.add_node("classify", self._node_classify)
        workflow.add_node("account", self._node_account)
        workflow.add_node("general", self._node_general)
        workflow.add_node("product", self._node_product)
        workflow.add_node("compliance", self._node_compliance)
        workflow.add_node("human", self._node_human)
        workflow.add_node("end", self._node_end)

        # Entry point
        workflow.set_entry_point("classify")

        # Conditional routing from classifier
        workflow.add_conditional_edges(
            "classify",
            self._route_by_intent,
            {
                "account": "account",
                "general": "general",
                "product": "product",
                "complaint": "human",
                "default": "general",
            }
        )

        # Route product recommendations to compliance check
        workflow.add_edge("product", "compliance")

        # All paths eventually end
        workflow.add_edge("account", "end")
        workflow.add_edge("general", "end")
        workflow.add_edge("compliance", "end")
        workflow.add_edge("human", "end")

        # End state
        workflow.set_finish_point("end")

        return workflow

    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================

    async def _node_classify(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Classify intent."""
        self.logger.info("📋 Classifying message intent...")

        message = state.get("message")
        customer_id = state.get("customer_id")

        # Run intent classifier
        classification = await self.intent_classifier.process({
            "message": message,
        })

        # Extract intent
        intent = classification.metadata.get("intent", "general_inquiry")
        confidence = classification.metadata.get("confidence", 0.0)

        # Update state
        state["intent"] = intent
        state["intent_confidence"] = confidence
        state["classifier_response"] = classification.content

        self.logger.info(f"✅ Intent: {intent} (confidence: {confidence:.2f})")

        return state

    async def _node_account(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle account inquiries."""
        self.logger.info("🏦 Processing account inquiry...")

        message = state.get("message")
        customer_id = state.get("customer_id")

        # Run account agent
        response = await self.account_agent.process({
            "customer_id": customer_id,
            "message": message,
        })

        state["agent_type"] = "account"
        state["agent_response"] = response.content
        state["agent_metadata"] = response.metadata
        state["confidence"] = response.confidence

        self.logger.info(f"✅ Account query handled: {response.metadata.get('query_type')}")

        return state

    async def _node_general(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general inquiries."""
        self.logger.info("❓ Processing general inquiry...")

        message = state.get("message")

        # Run general agent
        response = await self.general_agent.process({
            "message": message,
        })

        state["agent_type"] = "general"
        state["agent_response"] = response.content
        state["agent_metadata"] = response.metadata
        state["confidence"] = response.confidence

        self.logger.info(f"✅ General inquiry handled: {response.metadata.get('source')}")

        return state

    async def _node_product(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle product recommendations."""
        self.logger.info("💼 Processing product inquiry...")

        message = state.get("message")
        customer_id = state.get("customer_id")

        # Run product recommender
        response = await self.product_agent.process({
            "customer_id": customer_id,
            "message": message,
        })

        state["agent_type"] = "product"
        state["agent_response"] = response.content
        state["agent_metadata"] = response.metadata
        state["confidence"] = response.confidence

        self.logger.info(f"✅ Product recommendation generated")

        return state

    async def _node_compliance(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance of product recommendations."""
        self.logger.info("⚖️ Checking FCA compliance...")

        agent_response = state.get("agent_response")

        # Run compliance checker
        response = await self.compliance_agent.process({
            "content": agent_response,
            "product_type": state.get("agent_metadata", {}).get("product_type"),
        })

        state["compliance_check"] = response.content
        state["is_compliant"] = response.metadata.get("is_compliant", True)
        state["required_disclaimers"] = response.metadata.get("required_disclaimers", [])

        # Append disclaimers to agent response if not compliant
        if not state["is_compliant"]:
            disclaimers = "\n\n".join(state["required_disclaimers"])
            state["agent_response"] = f"{agent_response}\n\n⚠️ Important:\n{disclaimers}"

        self.logger.info(f"✅ Compliance check: {'✅ PASS' if state['is_compliant'] else '❌ NEEDS REVISION'}")

        return state

    async def _node_human(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Escalate to human agent."""
        self.logger.info("👤 Escalating to human specialist...")

        message = state.get("message")
        customer_id = state.get("customer_id")
        conversation_id = state.get("conversation_id", 0)

        # Run human agent
        response = await self.human_agent.process({
            "message": message,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
        })

        state["agent_type"] = "human"
        state["agent_response"] = response.content
        state["agent_metadata"] = response.metadata
        state["confidence"] = response.confidence

        self.logger.info(f"✅ Escalation created: {response.metadata.get('escalation_id')}")

        return state

    async def _node_end(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Final response formatting."""
        self.logger.info("📤 Formatting final response...")

        # Build final response object
        state["final_response"] = {
            "message": state.get("agent_response"),
            "agent": state.get("agent_type"),
            "intent": state.get("intent"),
            "confidence": state.get("confidence"),
            "metadata": {
                "intent_confidence": state.get("intent_confidence"),
                "agent_metadata": state.get("agent_metadata"),
                "is_compliant": state.get("is_compliant", True),
                "escalation_id": state.get("agent_metadata", {}).get("escalation_id"),
            }
        }

        self.logger.info("✅ Response ready to send")

        return state

    # ========================================================================
    # ROUTING LOGIC
    # ========================================================================

    def _route_by_intent(self, state: Dict[str, Any]) -> str:
        """Route to agent based on intent."""
        intent = state.get("intent", "general_inquiry")

        intent_map = {
            "account_inquiry": "account",
            "general_inquiry": "general",
            "product_inquiry": "product",
            "complaint": "complaint",
        }

        return intent_map.get(intent, "general")

    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================

    async def process_message(
        self,
        message: str,
        customer_id: int,
        conversation_id: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process message through workflow.

        Args:
            message: Customer message
            customer_id: Customer ID
            conversation_id: Conversation ID
            context: Optional context with services

        Returns:
            dict: Final response with agent info
        """
        self.logger.info(f"\n🔄 Processing message from customer {customer_id}")
        self.logger.info(f"Message: {message[:100]}...")

        # Initial state
        initial_state = {
            "message": message,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "context": context or {},
        }

        # Run workflow
        final_state = await self.workflow.ainvoke(initial_state)

        return final_state.get("final_response")

    def get_workflow_info(self) -> Dict[str, Any]:
        """Get workflow information."""
        return {
            "agents": [
                "IntentClassifier",
                "AccountAgent",
                "GeneralAgent",
                "ProductAgent",
                "ComplianceChecker",
                "HumanAgent",
            ],
            "flow": [
                "START",
                "  ↓",
                "CLASSIFY (IntentClassifier)",
                "  ├→ ACCOUNT (AccountAgent)",
                "  ├→ GENERAL (GeneralAgent)",
                "  ├→ PRODUCT (ProductAgent) → COMPLIANCE (ComplianceChecker)",
                "  └→ HUMAN (HumanAgent)",
                "  ↓",
                "END (Response Formatting)",
            ],
            "intents": [
                "account_inquiry",
                "general_inquiry",
                "product_inquiry",
                "complaint",
            ],
        }
