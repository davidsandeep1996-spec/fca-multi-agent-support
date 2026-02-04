"""
Agent Coordinator

Manages conversation state, routing, and persistence.
Coordinates multi-agent responses across conversation turns.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from langfuse import observe
from langgraph.checkpoint.memory import MemorySaver

from app.services.security_service import SecurityService

from app.workflows.message_workflow import MessageWorkflow
from app.database import AsyncSessionLocal
from app.services import (
            AccountService,
            CustomerService,
            ProductService,
            ConversationService,
            TransactionService,
            FAQService,
            MessageService
        )
from app.models.message import MessageRole

class ConversationMessage(BaseModel):
    """Single message in conversation."""

    customer_id: int
    message: str
    agent_type: str
    response: str
    intent: str
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)



class ConversationContext(BaseModel):
    """Maintains conversation state and history."""

    customer_id: int
    conversation_id: int
    messages: List[ConversationMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_intent: Optional[str] = None
    escalation_id: Optional[str] = None
    is_escalated: bool = False

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

    def get_llm_history(self, limit_turns: int = 5) -> List[Dict[str, str]]:
        """
        Get history formatted for LLM context (Sliding Window).
        Returns list of {'role': 'user'|'assistant', 'content': ...}
        """
        history = []
        # Get last N turns
        recent_msgs = self.messages[-limit_turns:]

        for msg in recent_msgs:
            # Add User Message
            history.append({"role": "user", "content": msg.message})
            # Add Agent Response
            history.append({"role": "assistant", "content": msg.response})

        return history

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

    def __init__(self,
    account_service=None,
    customer_service=None,
    product_service=None,
    conversation_service=None,
                 ):
        """Initialize coordinator."""
        self.logger = logging.getLogger(__name__)
        self.conversations: Dict[int, ConversationContext] = {}

            # Initialize services


        self.account_service = account_service or AccountService()
        self.customer_service = customer_service or CustomerService()
        self.product_service = product_service or ProductService()
        self.conversation_service = conversation_service or ConversationService()
        self.transaction_service = TransactionService()
        self.faq_service = FAQService()

        self.checkpointer = MemorySaver()



        self.security_service = SecurityService()

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
    @observe(name="AgentCoordinator")
    async def process_message(self, message: str, customer_id: int, conversation_id: int, context=None):

        sanitized_message = self.security_service.sanitize_input(message)

        self.logger.info(f"\n🔄 Coordinating message for customer {customer_id}")

        self.logger.info(f"Message: {sanitized_message}")

        conv_context = self.get_or_create_conversation(customer_id, conversation_id)

        history = conv_context.get_llm_history(limit_turns=5)

        if context is None:
            context = {}


        # Ensure Conversation Exists in DB before saving messages
        async with AsyncSessionLocal() as session:
            conv_svc = ConversationService(db=session)
            existing_conv = await conv_svc.get_conversation(conversation_id)
            if not existing_conv:
                self.logger.info(f"🆕 Creating new conversation {conversation_id} in DB")
                # Auto-create if missing (e.g., first message in new chat)
                # Note: We assume customer_id exists. If not, this might fail,
                # but usually customer is validated upstream (Auth).
                try:
                    new_conv = await conv_svc.start_conversation(
                        customer_id=customer_id,
                        title="New Conversation",
                        channel="web" # or ConversationChannel.WEB
                    )
                    await session.commit()
                    conversation_id = new_conv.id
                    self.logger.info(f"✅ Created conversation {conversation_id} for customer {customer_id}")
                except Exception as e:
                    self.logger.warning(f"Could not auto-create conversation: {e}")
                    await session.rollback()

        # [FIX] 1. Save User Message (Separate Session)
        async with AsyncSessionLocal() as session:
            msg_svc = MessageService(db=session)
            try:
                await msg_svc.add_message(
                    conversation_id=conversation_id,
                    role=MessageRole.CUSTOMER,
                    content=sanitized_message,
                    intent=None
                )
                await session.commit()
            except Exception as e:
                self.logger.error(f"Failed to save user message: {e}")

                await session.rollback()

            # build workflow WITH db-backed services
            workflow = MessageWorkflow(
                account_service=AccountService(db=session),
                customer_service=CustomerService(db=session),
                transaction_service=TransactionService(db=session),
                product_service=ProductService(db=session),
                conversation_service=ConversationService(db=session),
                faq_service=FAQService(db=session),
                checkpointer=self.checkpointer
            )

            # IMPORTANT: update context with the db-backed services (not self.*)
            #context.update({
             #   "account_service": AccountService(),
              #  "customer_service": CustomerService(),
               # "transaction_service": TransactionService(),
                #"product_service": ProductService(),
                # keep these only if they exist and are DB-safe in your project:
                # "compliance_service": ...,
               # "conversation_service": ConversationService(),
           #})

            # IMPORTANT: call the local workflow, not self.workflow
            workflow_response = await workflow.process_message(
                message=sanitized_message,
                customer_id=customer_id,
                conversation_id=conversation_id,
                context=context,
                history=history,
            )

        #  Handle Paused State
        if workflow_response.get("status") == "paused":
            # We can save a placeholder message or just notify
            self.logger.info(f"🛑 Conversation {conversation_id} is PAUSED for review.")
            # We might want to mark the conversation as 'review_pending' in DB here

            # Proceed to save the "Hold on" message to DB so user sees it
            response_text = workflow_response.get("response")
            # ... allow normal saving of this response ...

        # everything below stays the same (uses workflow_response)
        agent_type = workflow_response.get("agent","system")
        response_text = workflow_response.get("message") or workflow_response.get("response") or "Processing..."
        intent = workflow_response.get("intent")
        confidence = workflow_response.get("confidence", 0.0)

        # 2. Save Agent Response to DB
        async with AsyncSessionLocal() as session:
            msg_svc = MessageService(db=session)
            try:
                await msg_svc.add_message(
                    conversation_id=conversation_id,
                    role=MessageRole.AGENT,
                    content=response_text,
                    agent_name=agent_type,
                    intent=intent,
                    confidence_score=int(confidence * 100) if confidence else 0
                )
                await session.commit()
            except Exception as e:
                self.logger.error(f"Failed to save agent message: {e}")
                await session.rollback()

        conv_context.add_message(
            message=message,
            agent_type=agent_type,
            response=response_text,
            intent=intent,
            confidence=confidence,
        )

        escalation_id = workflow_response.get("metadata", {}).get("escalation_id")
        if escalation_id:
            conv_context.mark_escalated(escalation_id)
            self.logger.info(f"⚠️ Escalation detected: {escalation_id}")


        self.logger.info(f"✅ Message processed: {agent_type} agent, turn #{len(conv_context.messages)}")


        return {
            "response": response_text,
            "agent": agent_type,
            "intent": intent,
            "confidence": confidence,
            "conversation_id": conversation_id,
            "turn_count": len(conv_context.messages),
            "escalated": conv_context.is_escalated,
            "escalation_id": escalation_id,
            "status": workflow_response.get("status") or "success",
            "metadata": workflow_response.get("metadata", {}),
        }



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

    async def stream_message(self, message: str, customer_id: int, conversation_id: int, context=None):
        """
        Stream conversation updates (Server-Sent Events).
        Yields: Dicts with 'type', 'step', and 'content'.
        """
        conv_context = self.get_or_create_conversation(customer_id, conversation_id)

        if context is None: context = {}

        # 1. Manage DB Session manually for the generator
        async with AsyncSessionLocal() as session:
            # Initialize Services
            account_svc = AccountService(db=session)
            customer_svc = CustomerService(db=session)
            transaction_svc = TransactionService(db=session)
            product_svc = ProductService(db=session)
            conversation_svc = ConversationService(db=session)
            faq_svc = FAQService(db=session)

            # Build Workflow
            workflow = MessageWorkflow(
                account_service=account_svc,
                customer_service=customer_svc,
                transaction_service=transaction_svc,
                product_service=product_svc,
                conversation_service=conversation_svc,
                faq_service=faq_svc
            )

            # Update Context
            context.update({
                "account_service": account_svc,
                "customer_service": customer_svc,
                "transaction_service": transaction_svc,
                "product_service": product_svc,
                "conversation_service": conversation_svc,
            })

            # Track final state for persistence
            final_response_text = ""
            final_agent = "unknown"
            final_intent = "unknown"
            final_confidence = 0.0
            escalation_id = None

            # 2. Stream Loop
            async for node_name, state_update in workflow.process_message_stream(
                message, customer_id, conversation_id, context
            ):
                # --- EVENT: Intent Classified ---
                if node_name == "classify":
                    final_intent = state_update.get("intent")
                    yield {
                        "type": "status",
                        "step": "intent",
                        "content": f"Identified intent: {final_intent}"
                    }

                # --- EVENT: Agent Working ---
                elif node_name in ["account", "general", "product", "human"]:
                    final_agent = node_name
                    # Send a "thinking" update
                    yield {
                        "type": "status",
                        "step": "processing",
                        "content": f"{node_name.capitalize()} Agent is processing..."
                    }

                # --- EVENT: Compliance Check ---
                elif node_name == "compliance":
                     yield {
                        "type": "status",
                        "step": "compliance",
                        "content": "Verifying FCA compliance..."
                    }

                # --- EVENT: Final Response ---
                elif node_name == "end":
                    final_data = state_update.get("final_response", {})
                    final_response_text = final_data.get("message")
                    final_agent = final_data.get("agent")
                    final_intent = final_data.get("intent")
                    final_confidence = final_data.get("confidence")
                    escalation_id = final_data.get("metadata", {}).get("escalation_id")

                    yield {
                        "type": "response",
                        "content": final_response_text,
                        "metadata": final_data.get("metadata"),
                        "conversation_id": conversation_id
                    }

            # 3. Persistence (Save to Memory & DB)
            # This ensures history is saved even when streaming
            conv_context.add_message(
                message=message,
                agent_type=final_agent,
                response=final_response_text,
                intent=final_intent,
                confidence=final_confidence,
            )

            if escalation_id:
                conv_context.mark_escalated(escalation_id)

            self.logger.info(f"✅ Stream complete: {final_agent} agent")


    async def get_db_conversation_history(self, conversation_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch conversation history from the Database.
        """
        async with AsyncSessionLocal() as session:
            msg_service = MessageService(db=session)
            self.logger.info(f"🔍 Querying DB for History of Conversation {conversation_id}")

            messages = await msg_service.get_conversation_messages(conversation_id, page_size=limit)

            self.logger.info(f"🔍 DB Returned {len(messages)} messages for ID {conversation_id}")

            # Convert SQLAlchemy models to clean dicts
            history = []
            for msg in messages:
                # Handle potential Enum or String for role
                role_str = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)

                history.append({
                    "id": msg.id,
                    "role": role_str,
                    "content": msg.content,
                    "agent_name": msg.agent_name,
                    "intent": msg.intent,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None
                })

            # Sort by ID or Timestamp (Ascending = Chronological)
            history.sort(key=lambda x: x["timestamp"] or "")
            return history

    async def get_db_customer_conversations(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Fetch all conversations for a customer from Database.
        """
        async with AsyncSessionLocal() as session:
            conv_service = ConversationService(db=session)
            conversations = await conv_service.get_customer_conversations(customer_id)

            return [
                {
                    "conversation_id": c.id,
                    "title": c.title,
                    "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
                    "created_at": c.created_at.isoformat(),
                    "message_count": c.message_count,
                    "last_updated": c.updated_at.isoformat()
                }
                for c in conversations
            ]

    # Approve/Resume Workflow


    async def approve_intervention(self, conversation_id: int, new_response: str) -> Dict[str, Any]:
        """
        Admin approves (and edits) the response, then resumes the graph.
        """
        config = {"configurable": {"thread_id": str(conversation_id)}}

        # 1. Re-instantiate workflow
        workflow_wrapper = MessageWorkflow(
            account_service=AccountService(),
            customer_service=CustomerService(),
            transaction_service=TransactionService(),
            product_service=ProductService(),
            conversation_service=ConversationService(),
            faq_service=FAQService(),
            checkpointer=self.checkpointer
        )

        # [FIX] Fetch current state to satisfy Pydantic validation requirements
        snapshot = workflow_wrapper.workflow.get_state(config)
        if not snapshot.values:
             raise ValueError(f"No state found for conversation {conversation_id}")

        # Merge existing state with our updates
        # Ensure we work with a dictionary
        current_state = snapshot.values
        if hasattr(current_state, "model_dump"):
            current_state = current_state.model_dump()
        elif hasattr(current_state, "dict"):
            current_state = current_state.dict()

        # Create full payload (Original State + Updates)
        update_payload = current_state.copy()
        update_payload.update({
            "agent_response": new_response,
            "is_compliant": True,
            "required_disclaimers": []
        })

        # 2. Update State (Now passing FULL object)
        workflow_wrapper.workflow.update_state(
            config,
            update_payload
        )

        self.logger.info(f"✅ Admin updated state for {conversation_id}. Resuming...")

        # 3. Resume (Call None to proceed from interrupt)
        final_state = await workflow_wrapper.workflow.ainvoke(None, config=config)

        # 4. Save the Final Approved Response to DB
        response_data = final_state.get("final_response", {})
        async with AsyncSessionLocal() as session:
            msg_svc = MessageService(db=session)
            await msg_svc.add_message(
                conversation_id=conversation_id,
                role=MessageRole.AGENT,
                content=response_data.get("message"),
                agent_name=response_data.get("agent"),
                intent=response_data.get("intent"),
                confidence_score=99
            )

        return response_data
