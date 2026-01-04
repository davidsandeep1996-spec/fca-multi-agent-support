"""
Agents Package

Multi-agent system for FCA financial services support.
"""

from app.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.agents.intent_classifier import IntentClassifierAgent
from app.agents.product_recommender import ProductRecommenderAgent
from app.agents.compliance_checker import ComplianceCheckerAgent
from app.agents.general_agent import GeneralAgent
from app.agents.account_agent import AccountAgent
from app.agents.human_agent import HumanAgent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResponse",
    "IntentClassifierAgent",
    "ProductRecommenderAgent",
    "ComplianceCheckerAgent",
    "AccountAgent",
    "GeneralAgent",
    "HumanAgent",
]
