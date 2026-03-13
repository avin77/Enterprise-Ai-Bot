"""
Type definitions for the multi-agent routing pipeline (Phase 1.5).

These Pydantic models define the data contracts between agents:
- Message: a single conversation turn (user or assistant)
- RoutingDecision: the output of OrchestratorAgent.route()
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Intent label literals (logged for analytics, soft routing signal)
# ---------------------------------------------------------------------------
IntentLabel = Literal[
    "property_tax",
    "utility_services",
    "permits",
    "trash_waste",
    "voting",
    "court_fees",
    "benefits",
    "parks",
    "emergency",
    "general_info",
    "out_of_scope",
    # error sentinel — returned when OrchestratorAgent encounters an exception
    "error",
]

# Routing target literals (hard routing control)
RoutingTarget = Literal["retrieval", "tool", "fallback"]


# ---------------------------------------------------------------------------
# Message — a single conversation turn stored in history
# ---------------------------------------------------------------------------
class Message(BaseModel):
    """A single turn in the conversation history.

    Used to build the 5-turn context window passed to agent calls.
    """

    model_config = ConfigDict(validate_assignment=True)

    role: Literal["user", "assistant"] = Field(
        ..., description="Speaker role; must alternate user/assistant"
    )
    content: str = Field(..., description="Raw text of the message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC time this message was created",
    )


# ---------------------------------------------------------------------------
# RoutingDecision — output of OrchestratorAgent.route()
# ---------------------------------------------------------------------------
class RoutingDecision(BaseModel):
    """The routing decision returned by OrchestratorAgent.

    Serialised as JSON by the Bedrock haiku call and then validated here.

    Fields
    ------
    intent
        Soft intent label for analytics/dashboards. Does NOT directly
        control routing flow — routing_target does.
    confidence
        Float in [0, 1]. Values < 0.7 are coerced to routing_target
        'fallback' by OrchestratorAgent after parsing.
    routing_target
        Hard routing signal:
        - 'retrieval': informational query → BM25 RAG path
        - 'tool': transactional query → MockToolAgent (Phase 5: real APIs)
        - 'fallback': low-confidence, out-of-scope, or ambiguous
    reasoning
        One-sentence rationale from the model (logged for debugging).
    """

    model_config = ConfigDict(validate_assignment=True)

    intent: str = Field(
        ...,
        description="Intent label for analytics (one of the 11 IntentLabel options)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Routing confidence in [0, 1]",
    )
    routing_target: RoutingTarget = Field(
        ...,
        description="Hard routing target: retrieval | tool | fallback",
    )
    reasoning: str = Field(
        ...,
        description="One-sentence rationale from the model",
    )
