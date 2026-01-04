from app.agents.base import BaseAgent, AgentConfig, AgentResponse

# Test AgentConfig
config = AgentConfig(temperature=0.5, max_tokens=512)
config.to_dict()
{'model_name': 'mixtral-8x7b-32768', 'temperature': 0.5, 'max_tokens': 512, 'timeout': 30}

# Test AgentResponse
response = AgentResponse(
    content="Test response",
    confidence=0.9,
    agent_name="test_agent"
)
response.to_dict()
{'content': 'Test response', 'metadata': {}, 'confidence': 0.9, }

# Test abstract class (should fail)
try:
    agent = BaseAgent("test")
except TypeError as e:
    print(f"Expected error: {e}")
