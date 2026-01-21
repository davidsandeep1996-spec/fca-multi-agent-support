"""
Message Workflow

Multi-agent orchestration using LangGraph.
Routes messages through Intent Classifier → Specialized Agents.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
import logging

from langgraph.graph import StateGraph, END
from app.schemas.common import WorkflowState
from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.account_agent import AccountAgent
from app.agents.general_agent import GeneralAgent
from app.agents.human_agent import HumanAgent
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.compliance_checker import ComplianceCheckerAgent
from app.services import (
    AccountService,
    CustomerService,
    TransactionService,
    ProductService,
    ConversationService,
    FAQService,
)





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

    def __init__(self, *, account_service, customer_service, transaction_service, product_service, conversation_service, faq_service):
        self.intent_classifier = IntentClassifierAgent()
        self.account_agent = AccountAgent(
            account_service=account_service,
            customer_service=customer_service,
            transaction_service=transaction_service,
            faq_service=faq_service
        )
        self.general_agent = GeneralAgent(faq_service=faq_service)
        self.product_agent = ProductRecommenderAgent(product_service=product_service)
        self.compliance_agent = ComplianceCheckerAgent()
        self.human_agent = HumanAgent(conversation_service=conversation_service)
        self.logger = logging.getLogger(__name__)


        # Build LangGraph workflow
        self.graph = self._build_graph()
        self.workflow = self.graph.compile()

    def _build_graph(self):
        """Build LangGraph state machine."""

        # Create state graph
        workflow = StateGraph(WorkflowState)

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

    async def _node_classify(self, state: WorkflowState) -> Dict[str, Any]:
        """Classify intent."""
        self.logger.info("📋 Classifying message intent...")


        # customer_id = state.customer_id (not needed for classification logic, but available)

        # 2. PROCESS
        classification = await self.intent_classifier.process({
            "message": state.message,
        },context={"conversation_history": state.history})

        intent = classification.metadata.get("intent", "general_inquiry")
        confidence = classification.confidence

        self.logger.info(f"✅ Intent: {intent} (confidence: {confidence:.2f})")

        # 3. RETURN UPDATES (LangGraph merges this into the Pydantic model for you)
        return {
            "intent": intent,
            "intent_confidence": confidence,
            "classifier_response": classification.content
        }

    async def _node_account(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle account inquiries."""
        self.logger.info("🏦 Processing account inquiry...")

        # 1. READ (Dot notation is correct here)
        message = state.message
        customer_id = state.customer_id

        # 2. PROCESS
        response = await self.account_agent.process({
            "customer_id": customer_id,
            "message": message,
        },context={"conversation_history": state.history})

        self.logger.info(f"✅ Account query handled: {response.metadata.get('query_type')}")

        # 3. RETURN UPDATES (Return a dict, do not mutate state)
        return {
            "agent_type": "account",
            "agent_response": response.content,
            "agent_metadata": response.metadata,
            "confidence": response.confidence
        }
    async def _node_general(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle general inquiries."""
        self.logger.info("❓ Processing general inquiry...")

        # 1. READ from State
        message = state.message

        # 2. PROCESS
        response = await self.general_agent.process({
            "message": message,
        },context={"conversation_history": state.history})

        self.logger.info(f"✅ General inquiry handled: {response.metadata.get('source')}")

        # 3. RETURN UPDATES
        return {
            "agent_type": "general",
            "agent_response": response.content,
            "agent_metadata": response.metadata,
            "confidence": response.confidence
        }

    async def _node_product(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle product recommendations."""
        self.logger.info("💼 Processing product inquiry...")

        # 1. READ from State
        message = state.message
        customer_id = state.customer_id

        # 2. PROCESS
        response = await self.product_agent.process({
            "customer_id": customer_id,
            "message": message,
        },context={"conversation_history": state.history})

        self.logger.info(f"✅ Product recommendation generated")

        # 3. RETURN UPDATES
        return {
            "agent_type": "product",
            "agent_response": response.content,
            "agent_metadata": response.metadata,
            "confidence": response.confidence
        }

    async def _node_compliance(self, state: WorkflowState) -> Dict[str, Any]:
        """Check compliance of product recommendations."""
        self.logger.info("⚖️ Checking FCA compliance...")

        # 1. READ from State
        agent_response = state.agent_response
        products = state.agent_metadata.get("products")

        # 2. PROCESS
        response = await self.compliance_agent.process({
            "content": agent_response,
            "product_type": products,
        })

        is_compliant = response.metadata.get("is_compliant")
        required_disclaimers = response.metadata.get("required_disclaimers", [])

        # Prepare updates
        updates = {
            "compliance_check": response.content,
            "is_compliant": is_compliant,
            "required_disclaimers": required_disclaimers
        }

        # Logic: Append disclaimers to agent response if not compliant
        if not is_compliant:
            disclaimers = "\n\n".join(required_disclaimers)
            updates["agent_response"] = f"{agent_response}\n\n⚠️ Important:\n{disclaimers}"

        self.logger.info(f"✅ Compliance check: {'✅ PASS' if is_compliant else '❌ NEEDS REVISION'}")

        # 3. RETURN UPDATES
        return updates

    async def _node_human(self, state: WorkflowState) -> Dict[str, Any]:
        """Escalate to human agent."""
        self.logger.info("👤 Escalating to human specialist...")

        # 1. READ from State
        message = state.message
        customer_id = state.customer_id
        conversation_id = state.conversation_id
        context = state.context

        # 2. PROCESS
        response = await self.human_agent.process({
            "message": message,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
        }, context=context)

        self.logger.info(f"✅ Escalation created: {response.metadata.get('escalation_id')}")

        # 3. RETURN UPDATES
        return {
            "agent_type": "human",
            "agent_response": response.content,
            "agent_metadata": response.metadata,
            "confidence": response.confidence
        }

    async def _node_end(self, state: WorkflowState) -> Dict[str, Any]:
        """Final response formatting."""
        self.logger.info("📤 Formatting final response...")

        # 1. CONSTRUCT FINAL RESPONSE (Reading from Pydantic state)
        final_response = {
            "message": state.agent_response,
            "agent": state.agent_type,
            "intent": state.intent,
            "confidence": state.confidence,
            "metadata": {
                "intent_confidence": state.intent_confidence,
                "agent_metadata": state.agent_metadata,
                "is_compliant": state.is_compliant,
                "escalation_id": state.agent_metadata.get("escalation_id"),
            }
        }

        self.logger.info("✅ Response ready to send")

        # 3. RETURN UPDATES
        return {"final_response": final_response}

    # ========================================================================
    # ROUTING LOGIC
    # ========================================================================

    def _route_by_intent(self, state: WorkflowState) -> str:
        """Route to agent based on intent."""
        intent = state.intent or "general_inquiry"

        intent_map = {
            "account_inquiry": "account",
            "general_inquiry": "general",
            "loan_inquiry": "product",
            "credit_card": "product",
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
        history: List[Dict[str, str]] = None
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
            "history": history or []
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
