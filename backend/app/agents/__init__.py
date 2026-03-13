"""
backend.app.agents — multi-agent routing pipeline (Phase 1.5).

Public exports for easy import throughout the application:

    from backend.app.agents import OrchestratorAgent, RoutingDecision
    from backend.app.agents import RetrievalAgent, ResponseAgent, ChunkResult
    from backend.app.agents import MockMemoryStore, MockToolAgent
    from backend.app.agents import emit_trace_event, IntentConfusionMatrix
"""

from backend.app.agents.memory import ConversationTurn, MemoryStore, MockMemoryStore
from backend.app.agents.orchestrator import OrchestratorAgent
from backend.app.agents.response import ResponseAgent
from backend.app.agents.retrieval import ChunkResult, RetrievalAgent
from backend.app.agents.tool import MockToolAgent, ToolAgent, ToolResult
from backend.app.agents.tracer import IntentConfusionMatrix, emit_trace_event
from backend.app.agents.types import Message, RoutingDecision

__all__ = [
    # Core agents
    "OrchestratorAgent",
    "RetrievalAgent",
    "ResponseAgent",
    # Types
    "RoutingDecision",
    "Message",
    "ChunkResult",
    # Memory
    "MemoryStore",
    "MockMemoryStore",
    "ConversationTurn",
    # Tools
    "ToolAgent",
    "MockToolAgent",
    "ToolResult",
    # Observability
    "emit_trace_event",
    "IntentConfusionMatrix",
]
