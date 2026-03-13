"""
backend.app.agents — multi-agent routing pipeline (Phase 1.5).

Public exports for easy import throughout the application:

    from backend.app.agents import OrchestratorAgent, RoutingDecision
"""

from backend.app.agents.orchestrator import OrchestratorAgent
from backend.app.agents.types import Message, RoutingDecision

__all__ = [
    "OrchestratorAgent",
    "RoutingDecision",
    "Message",
]
