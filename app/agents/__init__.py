"""
Agents Package

Multi-agent system for FCA financial services support.
"""

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.agents.intent_classifier import IntentClassifierAgent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResponse",
    "IntentClassifierAgent",
]
