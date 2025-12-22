"""
Agents Package

Multi-agent system for FCA financial services support.
"""

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.product_recommender import ProductRecommenderAgent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResponse",
    "IntentClassifierAgent",
    "ProductRecommenderAgent",
]
