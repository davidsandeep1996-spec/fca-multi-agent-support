"""
Base Agent

Abstract base class for all agents in the multi-agent system.
Provides common functionality and interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from app.schemas.common import AgentResponse
from app.config import settings


class AgentConfig:
    """
    Agent configuration.

    Common configuration shared by all agents.
    """

    def __init__(
        self,
        model_name: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 30,
    ):
        """
        Initialize agent configuration.

        Args:
            model_name: LLM model to use
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            timeout: API timeout in seconds
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.api_key = settings.groq_api_key

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }



class BaseAgent(ABC):
    """
    Base agent class.

    All agents must inherit from this class and implement:
    - process() method for handling requests
    """

    def __init__(
        self,
        name: str,
        config: Optional[AgentConfig] = None,
        services: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name
            config: Agent configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or AgentConfig()
        self.logger = logging.getLogger(f"agent.{name}")
        self.services = services or {}

        # Agent metadata
        self.description = self._get_description()
        self.capabilities = self._get_capabilities()

        # Initialize agent
        self._initialize()

    # ========================================================================
    # ABSTRACT METHODS (must be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Process input and generate response.

        Args:
            input_data: Input data to process
            context: Optional context (conversation history, customer info, etc.)

        Returns:
            AgentResponse: Agent response
        """
        pass

    @abstractmethod
    def _get_description(self) -> str:
        """
        Get agent description.

        Returns:
            str: Agent description
        """
        pass

    @abstractmethod
    def _get_capabilities(self) -> List[str]:
        """
        Get agent capabilities.

        Returns:
            List[str]: List of capabilities
        """
        pass

    # ========================================================================
    # COMMON METHODS
    # ========================================================================

    def _initialize(self):
        """
        Initialize agent.

        Called after __init__. Override to add custom initialization.
        """
        self.logger.info(f"Initialized {self.name} agent")

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate input data.

        Args:
            input_data: Input to validate

        Returns:
            bool: True if valid

        Raises:
            ValueError: If input is invalid
        """
        if not input_data:
            raise ValueError("Input data cannot be empty")

        return True

    def log_request(self, input_data: Dict[str, Any]):
        """
        Log agent request.

        Args:
            input_data: Request input
        """
        self.logger.info(
            f"{self.name} processing request",
            extra={
                "agent": self.name,
                "input_keys": list(input_data.keys()),
            }
        )

    def log_response(self, response: AgentResponse):
        """
        Log agent response.

        Args:
            response: Agent response
        """
        self.logger.info(
            f"{self.name} generated response",
            extra={
                "agent": self.name,
                "confidence": response.confidence,
                "content_length": len(response.content),
            }
        )

    def create_response(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> AgentResponse:
        """
        Create standardized response.

        Args:
            content: Response content
            metadata: Additional metadata
            confidence: Confidence score

        Returns:
            AgentResponse: Formatted response
        """
        return AgentResponse(
            content=content,
            metadata=metadata,
            confidence=confidence,
            agent_name=self.name,
        )

    def get_info(self) -> Dict[str, Any]:
        """
        Get agent information.

        Returns:
            dict: Agent info
        """
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "config": self.config.to_dict(),
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__}(name='{self.name}')>"
