"""
Agent Coordinator (Enterprise Grade)

Stateless orchestration layer for multi-agent workflows.
Handles LangGraph execution, single-transaction persistence, SSE streaming,
and Postgres-backed thread pausing for Human-in-the-Loop escalations.
"""

from typing import Dict, Any, Optional, List
import logging
import asyncio
# Enterprise Checkpointing
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# SQLAlchemy & Models for direct DB aggregations
from sqlalchemy import select, func, update
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.security_service import SecurityService
from app.workflows.message_workflow import MessageWorkflow
from app.services.rag_service import RAGService
from app.services import (
    AccountService,
    CustomerService,
    ProductService,
    ConversationService,
    TransactionService,
    FAQService,
    MessageService,
)

class AgentCoordinator:
    """
    Coordinates multi-agent responses statelessly.

    Architecture:
    - 100% Stateless (No in-memory dictionaries)
    - Unit-of-Work DB Transactions (Single session per request)
    - Persistent Graph Checkpointing (AsyncPostgresSaver)
    - Deadlock-Free Connection Scoping
    """

    def __init__(self):
        """Initialize stateless coordinator."""
        self.logger = logging.getLogger(__name__)
        # Initialized globally as it requires no DB session
        self.security_service = SecurityService()

        # Kept pure for SQLAlchemy
        self.db_url = settings.database_url

        self._checkpointer_setup_done = False

    @property
    def _checkpointer_url(self) -> str:
        """
        Safely strips the SQLAlchemy dialect for LangGraph's native psycopg driver.
        Keeps the base db_url pure for other services.
        """
        return self.db_url.replace("+asyncpg", "")

    # ========================================================================
    # CORE ORCHESTRATION
    # ========================================================================

    async def process_message(
        self, message: str, customer_id: int, conversation_id: int, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        sanitized_message = self.security_service.sanitize_input(message)
        self.logger.info(f"\n🔄 Coordinating message for customer {customer_id} in conversation {conversation_id}")
        if context is None:
            context = {}

        self.logger.info("⏳ Attempting to open LangGraph Checkpointer...")

        # OPEN CHECKPOINTER
        async with AsyncPostgresSaver.from_conn_string(self._checkpointer_url) as checkpointer:
            self.logger.info("✅ Checkpointer connection opened.")

            # RUN SETUP ONLY ONCE
            if not self._checkpointer_setup_done:
                self.logger.info("⚙️ Running Checkpointer DDL Setup (First time only)...")
                try:
                    # 🚨 CIRCUIT BREAKER: Force a 30-second timeout on the DB lock
                    await asyncio.wait_for(checkpointer.setup(), timeout=30.0)
                    self._checkpointer_setup_done = True
                    self.logger.info("✅ Checkpointer DDL Setup complete.")
                except asyncio.TimeoutError:
                    self.logger.error("🚨 DATABASE DEADLOCK DETECTED! Another process is holding a lock.")
                    raise Exception("Database Deadlock during Checkpointer Setup. Please restart your DB container.")

            self.logger.info("⏳ Attempting to open SQLAlchemy Session...")

            # OPEN SQLALCHEMY TRANSACTION
            async with AsyncSessionLocal() as session:
                self.logger.info("✅ SQLAlchemy Session opened.")
                try:
                    conv_svc = ConversationService(db=session)
                    msg_svc = MessageService(db=session)

                    existing_conv = await conv_svc.get_conversation(conversation_id)
                    if not existing_conv:
                        new_conv = await conv_svc.start_conversation(
                            customer_id=customer_id, title="New Conversation", channel="web"
                        )
                        await session.flush()
                        conversation_id = new_conv.id

                    await msg_svc.add_message(
                        conversation_id=conversation_id, role=MessageRole.CUSTOMER, content=sanitized_message
                    )
                    await session.flush()

                    db_history = await msg_svc.get_conversation_messages(conversation_id, page_size=15)
                    history = [{"role": "user" if getattr(m, "role", "user") in ["customer", "user"] else "assistant",
                                "content": getattr(m, "content", "")} for m in db_history]

                    self.logger.info("⏳ Initializing MessageWorkflow...")
                    workflow = MessageWorkflow(
                        account_service=AccountService(db=session),
                        customer_service=CustomerService(db=session),
                        transaction_service=TransactionService(db=session),
                        product_service=ProductService(db=session),
                        conversation_service=conv_svc,
                        faq_service=FAQService(db=session),
                        rag_service=RAGService(),
                        checkpointer=checkpointer,
                    )

                    self.logger.info("🧠 Invoking LangGraph AI (Waiting for Groq API)...")

                    # Execute Graph
                    workflow_response = await workflow.process_message(
                        message=sanitized_message,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        context=context,
                        history=history,
                    )

                    self.logger.info("✅ LangGraph AI returned a response.")

                    is_escalated = False
                    escalation_id = workflow_response.get("metadata", {}).get("escalation_id")

                    if workflow_response.get("status") == "paused":
                        response_text = "Your request has been paused for human review."
                        agent_type = "system"
                        intent = "escalation"
                        confidence = 1.0
                        is_escalated = True
                    else:
                        agent_type = workflow_response.get("agent", "system")
                        response_text = workflow_response.get("message") or workflow_response.get("response") or "Processing..."
                        intent = workflow_response.get("intent")
                        confidence = workflow_response.get("confidence", 0.0)
                        if escalation_id:
                            is_escalated = True

                    await msg_svc.add_message(
                        conversation_id=conversation_id, role=MessageRole.AGENT, content=response_text,
                        agent_name=agent_type, intent=intent, confidence_score=int(confidence * 100) if confidence else 0,
                    )

                    await session.commit()
                    self.logger.info("✅ Database Transaction Committed.")

                    return {
                        "response": response_text, "agent": agent_type, "intent": intent,
                        "confidence": confidence, "conversation_id": conversation_id,
                        "turn_count": len(history) + 1, "escalated": is_escalated,
                        "escalation_id": escalation_id, "status": workflow_response.get("status") or "success",
                        "metadata": workflow_response.get("metadata", {}),
                    }

                except Exception as e:
                    await session.rollback()
                    self.logger.error(f"❌ Transaction Failed! Rolled back. Error: {e}")
                    raise e

    # ========================================================================
    # EVENT STREAMING
    # ========================================================================

    async def stream_message(
        self, message: str, customer_id: int, conversation_id: int, context: Optional[Dict[str, Any]] = None
    ):
        """Stream Server-Sent Events (SSE) while persisting to DB via Postgres Checkpointer."""
        sanitized_message = self.security_service.sanitize_input(message)
        if context is None:
            context = {}

        # 1. OPEN CHECKPOINTER FIRST
        async with AsyncPostgresSaver.from_conn_string(self._checkpointer_url) as checkpointer:
            self.logger.info("✅ Checkpointer connection opened.")

            # RUN SETUP ONLY ONCE
            if not self._checkpointer_setup_done:
                self.logger.info("⚙️ Running Checkpointer DDL Setup (First time only)...")
                try:
                    # 🚨 CIRCUIT BREAKER: Force a 5-second timeout on the DB lock
                    await asyncio.wait_for(checkpointer.setup(), timeout=30.0)
                    self._checkpointer_setup_done = True
                    self.logger.info("✅ Checkpointer DDL Setup complete.")
                except asyncio.TimeoutError:
                    self.logger.error("🚨 DATABASE DEADLOCK DETECTED! Another process is holding a lock.")
                    raise Exception("Database Deadlock during Checkpointer Setup. Please restart your DB container.")

            # 2. OPEN SQLALCHEMY TRANSACTION
            async with AsyncSessionLocal() as session:
                conv_svc = ConversationService(db=session)
                msg_svc = MessageService(db=session)

                await msg_svc.add_message(conversation_id=conversation_id, role=MessageRole.CUSTOMER, content=sanitized_message)
                await session.commit()

                workflow = MessageWorkflow(
                    account_service=AccountService(db=session),
                    customer_service=CustomerService(db=session),
                    transaction_service=TransactionService(db=session),
                    product_service=ProductService(db=session),
                    conversation_service=conv_svc,
                    faq_service=FAQService(db=session),
                    rag_service=RAGService(),
                    checkpointer=checkpointer,
                )

                async for node_name, state_update in workflow.process_message_stream(sanitized_message, customer_id, conversation_id, context):
                    if node_name == "classify":
                        yield {"type": "status", "step": "intent", "content": f"Identified intent: {state_update.get('intent')}"}
                    elif node_name in ["account", "general", "product", "human"]:
                        yield {"type": "status", "step": "processing", "content": f"{node_name.capitalize()} Agent is processing..."}
                    elif node_name == "compliance":
                        yield {"type": "status", "step": "compliance", "content": "Verifying FCA compliance..."}
                    elif node_name == "end":
                        final_data = state_update.get("final_response", {})

                        # Save final output in a new transaction
                        async with AsyncSessionLocal() as save_session:
                            final_msg_svc = MessageService(db=save_session)
                            await final_msg_svc.add_message(
                                conversation_id=conversation_id,
                                role=MessageRole.AGENT,
                                content=final_data.get("message"),
                                agent_name=final_data.get("agent"),
                                intent=final_data.get("intent")
                            )
                            await save_session.commit()

                        yield {
                            "type": "response",
                            "content": final_data.get("message"),
                            "metadata": final_data.get("metadata"),
                            "conversation_id": conversation_id,
                        }

    # ========================================================================
    # HUMAN IN THE LOOP
    # ========================================================================

    async def approve_intervention(self, conversation_id: int, new_response: str) -> Dict[str, Any]:
        """Admin approves/edits a paused thread. Uses Postgres Checkpointer to resume."""
        config = {"configurable": {"thread_id": str(conversation_id)}}

        # 1. OPEN CHECKPOINTER FIRST
        async with AsyncPostgresSaver.from_conn_string(self._checkpointer_url) as checkpointer:
            self.logger.info("✅ Checkpointer connection opened.")

            # RUN SETUP ONLY ONCE
            if not self._checkpointer_setup_done:
                self.logger.info("⚙️ Running Checkpointer DDL Setup (First time only)...")
                try:
                    # 🚨 CIRCUIT BREAKER: Force a 5-second timeout on the DB lock
                    await asyncio.wait_for(checkpointer.setup(), timeout=30.0)
                    self._checkpointer_setup_done = True
                    self.logger.info("✅ Checkpointer DDL Setup complete.")
                except asyncio.TimeoutError:
                    self.logger.error("🚨 DATABASE DEADLOCK DETECTED! Another process is holding a lock.")
                    raise Exception("Database Deadlock during Checkpointer Setup. Please restart your DB container.")

            # 2. OPEN SQLALCHEMY TRANSACTION
            async with AsyncSessionLocal() as session:
                workflow_wrapper = MessageWorkflow(
                    account_service=AccountService(db=session),
                    customer_service=CustomerService(db=session),
                    transaction_service=TransactionService(db=session),
                    product_service=ProductService(db=session),
                    conversation_service=ConversationService(db=session),
                    faq_service=FAQService(db=session),
                    rag_service=RAGService(),
                    checkpointer=checkpointer,
                )

                snapshot = await workflow_wrapper.workflow.aget_state(config)

                # ✅ FIX: Check if snapshot.next exists to prevent ghost interventions
                if not snapshot or not snapshot.values or not snapshot.next:
                    raise ValueError(f"No paused state found in DB for conversation {conversation_id}")

                # Update the state natively (force the agent type so _node_end formats it properly)
                await workflow_wrapper.workflow.aupdate_state(
                    config,
                    {
                        "agent_response": new_response,
                        "is_compliant": True,
                        "agent_type": "human_admin"
                    }
                )

                self.logger.info(f"✅ Admin injected state for {conversation_id}. Resuming Graph...")

                final_state = await workflow_wrapper.workflow.ainvoke(None, config=config)
                response_data = final_state.get("final_response", {})

                msg_svc = MessageService(db=session)
                await msg_svc.add_message(
                    conversation_id=conversation_id,
                    role=MessageRole.AGENT,
                    content=response_data.get("message"),
                    agent_name="human_admin",
                    intent=response_data.get("intent", "resolved")
                )
                await session.commit()

                return {
                    "message": new_response,
                    "agent": "human_admin",
                    "status": "success",
                    "intent": "resolved"
                }

    # ========================================================================
    # ESCALATION MANAGEMENT
    # ========================================================================

    async def get_escalated_conversations(self) -> List[Dict[str, Any]]:
        """Get all active escalated conversations reading directly from DB."""
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(
                Conversation.ticket_id.isnot(None)
            ).where(
                Conversation.status != "resolved"
            )
            result = await session.execute(stmt)
            escalated_records = result.scalars().all()

            return [{
                "conversation_id": conv.id,
                "customer_id": conv.customer_id,
                "ticket_id": getattr(conv, "ticket_id", None),
                "message_count": getattr(conv, "message_count", 0),
                "created_at": conv.created_at.isoformat(),
            } for conv in escalated_records]

    async def resolve_escalation(self, conversation_id: int, resolution_notes: str) -> bool:
        """Mark an escalation as resolved in the persistent Database."""

        async with AsyncSessionLocal() as session:
            try:
                # Directly update the conversation status to 'resolved'
                stmt = (
                    update(Conversation)
                    .where(Conversation.id == conversation_id)
                    .values(status="resolved")
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    self.logger.info(f"✅ Escalation resolved in DB for conversation {conversation_id}")
                    return True

                return False
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to resolve escalation: {e}")
                return False

    # ========================================================================
    # OBSERVABILITY & ANALYTICS
    # ========================================================================

    async def get_statistics(self) -> Dict[str, Any]:
        """Enterprise Dashboard Analytics via DB aggregations."""
        async with AsyncSessionLocal() as session:
            # Safely execute COUNT queries directly to prevent Missing Method errors
            total_convs = await session.scalar(select(func.count(Conversation.id)))

            escalated_convs = await session.scalar(
                select(func.count(Conversation.id)).where(Conversation.ticket_id.isnot(None))
            )

            total_msgs = await session.scalar(select(func.count(Message.id)))

            total_convs = total_convs or 0
            escalated_convs = escalated_convs or 0
            total_msgs = total_msgs or 0

            return {
                "total_conversations": total_convs,
                "total_messages": total_msgs,
                "escalated_conversations": escalated_convs,
                "avg_messages_per_conversation": (total_msgs / total_convs) if total_convs > 0 else 0,
                "architecture": "Stateless LangGraph Postgres Setup",
                "health": "Operational"
            }

    async def get_db_conversation_history(self, conversation_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch strict conversational payload for UI rendering."""
        async with AsyncSessionLocal() as session:
            msg_service = MessageService(db=session)
            messages = await msg_service.get_conversation_messages(conversation_id, page_size=limit)

            history = []
            for msg in messages:
                role_str = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
                history.append({
                    "id": msg.id,
                    "role": "user" if role_str == "customer" else role_str,
                    "content": msg.content,
                    "agent_name": msg.agent_name,
                    "intent": msg.intent,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                })

            history.sort(key=lambda x: x["timestamp"] or "")
            return history

    async def get_db_customer_conversations(self, customer_id: int) -> List[Dict[str, Any]]:
        """Fetch lightweight metadata for Customer Dashboard menus."""
        async with AsyncSessionLocal() as session:
            conv_service = ConversationService(db=session)
            conversations = await conv_service.get_customer_conversations(customer_id)

            return [{
                "conversation_id": c.id,
                "title": c.title,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "created_at": c.created_at.isoformat(),
                "message_count": getattr(c, "message_count", 0),
            } for c in conversations]

    def get_coordinator_info(self) -> Dict[str, Any]:
        """Get static coordinator metadata and health-check info."""
        return {
            "type": "AgentCoordinator",
            "workflow": "LangGraph (MessageWorkflow)",
            "architecture": "Stateless / Distributed",
            "persistence": "AsyncPostgresSaver & Unit-of-Work",
            "features": [
                "Multi-turn conversations",
                "Intent tracking",
                "Escalation management",
                "Conversation history",
                "Statistics & monitoring",
            ],
        }
