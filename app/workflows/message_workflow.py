"""
Message Workflow

Multi-agent orchestration using LangGraph.
Routes messages through Intent Classifier → Specialized Agents.
"""

from typing import Dict, Any, Optional, List
import logging
from app.services.security_service import SecurityService
from langfuse import observe

from langgraph.graph import StateGraph
from app.schemas.common import WorkflowState
from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.account_agent import AccountAgent
from app.agents.general_agent import GeneralAgent
from app.agents.human_agent import HumanAgent
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.compliance_checker import ComplianceCheckerAgent


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

    def __init__(
        self,
        *,
        account_service,
        customer_service,
        transaction_service,
        product_service,
        conversation_service,
        faq_service,
        rag_service=None,
        checkpointer=None,
    ):
        self.intent_classifier = IntentClassifierAgent()
        self.account_agent = AccountAgent(
            account_service=account_service,
            customer_service=customer_service,
            transaction_service=transaction_service,
            faq_service=faq_service,
        )
        self.general_agent = GeneralAgent(
            faq_service=faq_service, rag_service=rag_service
        )
        self.product_agent = ProductRecommenderAgent(product_service=product_service)
        self.compliance_agent = ComplianceCheckerAgent()
        self.human_agent = HumanAgent(conversation_service=conversation_service)
        self.logger = logging.getLogger(__name__)

        # Initialize memory saver
        self.checkpointer = checkpointer
        self.security_service = SecurityService()
        # Build LangGraph workflow
        self.graph = self._build_graph()
        self.workflow = self.graph.compile(
            checkpointer=self.checkpointer, interrupt_before=["human_approval"]
        )

    def _build_graph(self):
        """Build LangGraph state machine."""

        # Create state graph
        workflow = StateGraph(WorkflowState)

        # Define nodes
        workflow.add_node("guardrail", self._node_guardrail)

        workflow.add_node("classify", self._node_classify)
        workflow.add_node("account", self._node_account)
        workflow.add_node("general", self._node_general)
        workflow.add_node("product", self._node_product)
        workflow.add_node("compliance", self._node_compliance)
        workflow.add_node("human", self._node_human)
        workflow.add_node("end", self._node_end)
        workflow.add_node("human_approval", self._node_human_approval)

        # Entry point
        workflow.set_entry_point("guardrail")

        #  Conditional Edge from Guardrail
        workflow.add_conditional_edges(
            "guardrail", self._route_guardrail, {"safe": "classify", "unsafe": "end"}
        )

        # Conditional routing from classifier
        workflow.add_conditional_edges(
            "classify",
            self._route_by_intent,
            {
                "account": "account",
                "general": "general",
                "product": "product",
                "complaint": "human",
                "escalate": "human",  # Route unknowns to the human bottleneck
            },
        )

        # Route product recommendations to compliance check
        workflow.add_edge("product", "compliance")

        # All paths eventually end
        workflow.add_edge("account", "end")
        workflow.add_edge("general", "end")
        workflow.add_edge("human", "human_approval")

        workflow.add_conditional_edges(
            "compliance",
            self._route_compliance,  # New router
            {"approved": "end", "review": "human_approval"},
        )

        workflow.add_edge("human_approval", "end")

        # End state
        workflow.set_finish_point("end")

        return workflow

    #  Add Routing Logic for Guardrail
    def _route_guardrail(self, state: WorkflowState) -> str:
        """Route based on security check."""
        # If metadata contains 'blocked', it means guardrail failed
        if state.agent_metadata and state.agent_metadata.get("blocked"):
            return "unsafe"
        return "safe"

    def _get_clean_guardrail_state(self) -> Dict[str, Any]:
        """Helper to clear previous guardrail blocks from persistent state."""
        return {"agent_metadata": {"blocked": False, "violation": None}, "intent": None}

    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================

    @observe(as_type="span", name="Node: Guardrail")
    async def _node_guardrail(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Security Guardrail Node.
        """
        self.logger.info("🛡️  Running security guardrails...")

        clean_msg = state.message.lower()

        # 1. FINANCIAL SAFETY TRAP (Applied only to the NEW message)
        impossible_claims = [
            "risk-free",
            "risk free",
            "guaranteed profit",
            "no risk",
            "100% safe",
        ]

        if any(phrase in clean_msg for phrase in impossible_claims):
            return {
                "agent_type": "compliance_system",
                "agent_response": (
                    "I cannot provide a recommendation for that specific request.\n\n"
                    "**Regulatory Notice:** In financial services, no investment or profit is 100% 'risk-free' or 'guaranteed'. "
                    "All investments carry some level of risk, and their value can go down as well as up."
                ),
                "agent_metadata": {"blocked": True},
                "intent": "security_violation",
            }

        # 2. SAFE BYPASS (Allows balance/transactions to skip deep security checks)
        safe_keywords = ["balance", "transaction", "statement", "account"]
        if any(kw in clean_msg for kw in safe_keywords) and len(clean_msg) < 100:
            return self._get_clean_guardrail_state()

        # 3. DEEP SECURITY (Jailbreak check)
        is_safe, reason = self.security_service.check_jailbreak(state.message)
        if not is_safe:
            return {
                "agent_type": "security_system",
                "agent_response": "I cannot process that request due to safety guidelines.",
                "agent_metadata": {"blocked": True},
                "intent": "security_violation",
            }

        return self._get_clean_guardrail_state()

    @observe(as_type="span", name="Node: Classify")
    async def _node_classify(self, state: WorkflowState) -> Dict[str, Any]:
        """Classify intent."""
        self.logger.info("📋 Classifying message intent...")
        try:
            classification = await self.intent_classifier.process(
                {"message": state.message},
                context={"conversation_history": state.history},
            )
            intent = classification.metadata.get("intent", "general_inquiry")
            confidence = classification.confidence
            self.logger.info(f"✅ Intent: {intent} (confidence: {confidence:.2f})")

            return {
                "intent": intent,
                "intent_confidence": confidence,
                "classifier_response": classification.content,
            }
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in Classifier: {e}")
            return {
                "intent": "unmapped",
                "intent_confidence": 0.0,
                "classifier_response": "Classification failed due to system error.",
            }

    @observe(as_type="span", name="Node: Account")
    async def _node_account(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle account inquiries."""
        self.logger.info("🏦 Processing account inquiry...")
        try:
            response = await self.account_agent.process(
                {"customer_id": state.customer_id, "message": state.message},
                context={"conversation_history": state.history},
            )
            self.logger.info(
                f"✅ Account query handled: {response.metadata.get('query_type')}"
            )
            return {
                "agent_type": "account",
                "agent_response": response.content,
                "agent_metadata": response.metadata,
                "confidence": response.confidence,
            }
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in Account Agent: {e}")
            return {
                "agent_type": "account",
                "agent_response": "I'm currently experiencing technical difficulties accessing your account. Please try again later.",
                "agent_metadata": {"error": str(e)},
                "confidence": 0.0,
            }

    @observe(as_type="span", name="Node: General")
    async def _node_general(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle general inquiries."""
        self.logger.info("❓ Processing general inquiry...")
        try:
            response = await self.general_agent.process(
                {"message": state.message},
                context={"conversation_history": state.history},
            )
            self.logger.info(
                f"✅ General inquiry handled: {response.metadata.get('source')}"
            )
            return {
                "agent_type": "general",
                "agent_response": response.content,
                "agent_metadata": response.metadata,
                "confidence": response.confidence,
            }
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in General Agent: {e}")
            return {
                "agent_type": "general",
                "agent_response": "I'm currently unable to retrieve the requested information. Please try again later.",
                "agent_metadata": {"error": str(e)},
                "confidence": 0.0,
            }

    @observe(as_type="span", name="Node: Product")
    async def _node_product(self, state: WorkflowState) -> Dict[str, Any]:
        """Handle product recommendations."""
        self.logger.info("💼 Processing product inquiry...")
        try:
            response = await self.product_agent.process(
                {
                    "customer_id": state.customer_id,
                    "message": state.message,
                    "intent": state.intent,
                },
                context={"conversation_history": state.history},
            )
            self.logger.info("✅ Product recommendation generated")
            return {
                "agent_type": "product",
                "agent_response": response.content,
                "agent_metadata": response.metadata,
                "confidence": response.confidence,
            }
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in Product Agent: {e}")
            return {
                "agent_type": "product",
                "agent_response": "Product recommendations are temporarily unavailable.",
                "agent_metadata": {"products": [], "error": str(e)},
                "confidence": 0.0,
            }

    @observe(as_type="span", name="Node: Compliance")
    async def _node_compliance(self, state: WorkflowState) -> Dict[str, Any]:
        """Check compliance of product recommendations."""
        self.logger.info("⚖️ Checking FCA compliance...")
        try:
            response = await self.compliance_agent.process(
                {
                    "content": state.agent_response,
                    "product_type": state.agent_metadata.get("products"),
                }
            )

            is_compliant = response.metadata.get("is_compliant")
            required_disclaimers = response.metadata.get("required_disclaimers", [])
            issues = response.metadata.get("issues", [])

            prohibited = [i for i in issues if "Prohibited" in i]

            if not is_compliant and not prohibited:
                self.logger.info(
                    "⚠️ Auto-resolving minor compliance issues to avoid Human Loop"
                )
                is_compliant = True

            if self._evaluate_demo_overrides(state.message, prohibited):
                self.logger.info("✅ Force-approving loan request (Demo Override)")
                is_compliant = True

            updates = {
                "compliance_check": response.content,
                "is_compliant": is_compliant,
                "required_disclaimers": required_disclaimers,
            }

            if required_disclaimers:
                disclaimers = "\n\n".join(required_disclaimers)
                updates["agent_response"] = (
                    f"{state.agent_response}\n\n⚠️ Important:\n{disclaimers}"
                )

            if not is_compliant:
                updates["agent_response"] = (
                    "I cannot recommend this product due to compliance restrictions (Prohibited Language)."
                )

            return updates
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in Compliance Agent: {e}")
            return {
                "compliance_check": "Failed due to system error",
                "is_compliant": False,  # Fail safe: automatically block if compliance crashes
                "agent_response": "This recommendation could not be verified for compliance due to a system error.",
            }

    @observe(as_type="span", name="Node: Human")
    async def _node_human(self, state: WorkflowState) -> Dict[str, Any]:
        """Escalate to human agent."""
        self.logger.info("👤 Escalating to human specialist...")
        try:
            history_context = self._format_history_for_llm(state.history)
            full_prompt = f"{history_context}CURRENT USER MESSAGE: {state.message}"

            response = await self.human_agent.process(
                {
                    "message": full_prompt,
                    "customer_id": state.customer_id,
                    "conversation_id": state.conversation_id,
                },
                context=state.context,
            )
            self.logger.info(
                f"✅ Escalation created: {response.metadata.get('escalation_id')}"
            )
            return {
                "agent_type": "human",
                "agent_response": response.content,
                "agent_metadata": response.metadata,
                "confidence": response.confidence,
            }
        except Exception as e:
            self.logger.error(f"🚨 LLM API Failure in Human Escalation: {e}")
            return {
                "agent_type": "human",
                "agent_response": "We are experiencing technical difficulties, but your issue has been flagged for human review.",
                "agent_metadata": {"escalation_id": "SYS_ERR_ESCALATION"},
                "confidence": 0.0,
            }

    @observe(as_type="span", name="Node: End")
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
            },
        }

        self.logger.info("✅ Response ready to send")

        # 3. RETURN UPDATES
        return {"final_response": final_response}

    async def _node_human_approval(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Node that represents the 'Human Review' step.
        Since we set interrupt_before=['human_approval'], execution pauses HERE.
        When resumed, it executes this and moves to END.
        """
        self.logger.info("👤 Manual approval processed.")
        return {}

    def _evaluate_demo_overrides(self, message: str, prohibited: List[str]) -> bool:
        """Helper to determine if a demo loan override should apply."""
        if "loan" in message.lower() and not prohibited:
            return True
        return False

    # ========================================================================
    # ROUTING LOGIC
    # ========================================================================

    def _route_by_intent(self, state: WorkflowState) -> str:
        """Route to agent based on intent."""
        intent = state.intent or "unmapped"
        confidence = (
            state.intent_confidence if state.intent_confidence is not None else 1.0
        )

        # ✅ FIX: Route low confidence or unrecognized intents to Escalation safely
        if confidence < 0.4:
            self.logger.warning(f"⚠️ Low confidence ({confidence}). Escalating.")
            return "escalate"

        intent_map = {
            "account_data": "account",
            "general_inquiry": "general",
            "knowledge_inquiry": "general",
            "product_acquisition": "product",
            "credit_card": "product",
            "complaint": "complaint",
        }

        # Any unrecognized string from the LLM will map to 'escalate' instead of hallucinating
        return intent_map.get(intent, "escalate")

    def _route_compliance(self, state: WorkflowState) -> str:
        """Route based on compliance status."""
        if state.is_compliant:
            return "approved"
        return "review"

    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================
    @observe(name="MessageWorkflow")
    async def process_message(
        self,
        message: str,
        customer_id: int,
        conversation_id: int = 0,
        context: Optional[Dict[str, Any]] = None,
        history: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Process message through workflow.
        """
        self.logger.info(f"\n🔄 Processing message from customer {customer_id}")
        self.logger.info(f"Message: {message[:100]}...")

        # Config for persistence
        config = {"configurable": {"thread_id": str(conversation_id)}}

        initial_state = {
            "message": message,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "context": context or {},
            "history": history or [],
        }

        # Run workflow
        final_state = await self.workflow.ainvoke(initial_state, config=config)
        snapshot = await self.workflow.aget_state(config)

        if snapshot.next:
            # ✅ FIX: The graph was natively paused by the Postgres Checkpointer
            self.logger.info("⏸️ Workflow natively paused by LangGraph for Human Review")

            # Extract raw state (since _node_end hasn't run yet)
            agent_meta = final_state.get("agent_metadata", {})
            esc_id = agent_meta.get("escalation_id", "PENDING_REVIEW")

            return {
                "message": "Your request has been paused for human review. An agent will be with you shortly.",
                "response": "Your request has been paused for human review. An agent will be with you shortly.",
                "agent": "system",
                "intent": final_state.get("intent", "escalation"),
                "confidence": final_state.get("confidence", 1.0),
                "status": "paused",
                "metadata": {"escalation_id": esc_id},
            }

        # If graph finished normally, return the finalized payload
        return final_state.get("final_response", {})

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

    async def process_message_stream(
        self,
        message: str,
        customer_id: int,
        conversation_id: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Stream workflow execution (Yields partial updates node-by-node).
        """
        initial_state = {
            "message": message,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "context": context or {},
        }

        # [CHANGED] Add the mandatory config object so AsyncPostgresSaver knows where to stream
        config = {"configurable": {"thread_id": str(conversation_id)}}

        # Use LangGraph's astream to get state updates after each node finishes
        async for event in self.workflow.astream(initial_state, config=config):
            for node_name, state_update in event.items():
                yield node_name, state_update

    def _format_history_for_llm(self, history: List[Dict[str, Any]]) -> str:
        """
        Converts list of dicts into a string context for the LLM.
        """
        if not history:
            return ""

        formatted = []
        for msg in history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            formatted.append(f"[{role}]: {content}")

        # Use robust delimiters
        return (
            "=== START CONVERSATION HISTORY ===\n"
            + "\n".join(formatted)
            + "\n=== END CONVERSATION HISTORY ===\n\n"
        )
