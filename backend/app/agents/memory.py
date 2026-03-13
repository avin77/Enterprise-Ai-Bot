"""
MemoryStore — abstract interface + MockMemoryStore (no-op Phase 1.5 implementation).

DynamoDB voicebot_sessions Table Schema
=======================================
Table name  : voicebot_sessions
PK          : session_id  (String)
SK          : hashed_timestamp  (String)  — see hashed prefix logic below
TTL attr    : expiry_epoch  (Number, seconds since epoch = now + 90 days)

Hashed prefix logic (prevents hot partition):
    import hashlib
    prefix = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % 10
    sk = f"{prefix}#{timestamp_iso}"

All item attributes:
    session_id           (S)  PK
    hashed_timestamp     (S)  SK — e.g. "7#2026-03-13T12:00:00.000Z"
    expiry_epoch         (N)  TTL — Unix epoch seconds, now + 90 days

    turn_number          (N)  1-based turn counter within session
    user_input           (S)  Raw user utterance
    assistant_response   (S)  Scrubbed assistant response

    intent               (S)  Intent label from OrchestratorAgent
    intent_confidence    (N)  Float 0-1
    routing_target       (S)  retrieval | tool | fallback

    retrieved_doc_ids    (SS) Set of source doc IDs from RetrievalAgent
    rag_chunks_text      (S)  JSON-serialised list of chunk texts (truncated)

    asr_latency_ms       (N)
    rag_latency_ms       (N)
    orchestrator_latency_ms (N)
    response_latency_ms  (N)
    total_latency_ms     (N)

    llm_prompt_tokens    (N)
    llm_completion_tokens (N)

    completion_status    (S)  "complete" | "error" | "timeout"
    follow_up_detected   (BOOL)
    fallback_triggered   (BOOL)
    clarification_requested (BOOL)

    compute_cost_usd     (N)
    llm_cost_usd         (N)
    storage_cost_usd     (N)

    timestamp            (S)  ISO 8601 with Z, e.g. "2026-03-13T12:00:00Z"

Phase 2.5 upgrade path:
    Replace MockMemoryStore with DynamoDBMemoryStore that:
    - Reads/writes to voicebot_sessions DynamoDB table (schema above)
    - Injects last 5 turns into OrchestratorAgent context
    - Populates conversation metrics (session duration, turn count, cost totals)
    - Implements session expiry via TTL (90-day auto-delete)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in the conversation history stored in DynamoDB.

    Attributes:
        user_input: The user's utterance for this turn.
        assistant_response: The assistant's response.
        intent: Intent label from OrchestratorAgent routing decision.
        intent_confidence: Routing confidence float 0-1.
        routing_target: Which pipeline path was taken.
        timestamp: ISO 8601 UTC timestamp.
    """

    user_input: str
    assistant_response: str
    intent: str
    intent_confidence: float
    routing_target: str
    timestamp: str


class MemoryStore(ABC):
    """Abstract interface for conversation memory storage.

    Implementations:
    - MockMemoryStore  (Phase 1.5): no-op, always returns empty history
    - DynamoDBMemoryStore (Phase 2.5): reads/writes voicebot_sessions table
    """

    @abstractmethod
    async def get_history(
        self, session_id: str, max_turns: int = 5
    ) -> list[ConversationTurn]:
        """Retrieve the last max_turns conversation turns for a session."""
        raise NotImplementedError

    @abstractmethod
    async def write_turn(
        self, session_id: str, turn: ConversationTurn
    ) -> None:
        """Persist a single conversation turn to the memory store."""
        raise NotImplementedError

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete all turns for a session (e.g. on explicit logout)."""
        raise NotImplementedError


class MockMemoryStore(MemoryStore):
    """Phase 1.5 no-op memory store.

    Behaviour:
    - get_history() always returns [] — no history injection in Phase 1.5
    - write_turn() is a no-op — turns are not persisted
    - delete_session() is a no-op

    Phase 2.5 will replace this with DynamoDBMemoryStore.
    """

    async def get_history(
        self, session_id: str, max_turns: int = 5
    ) -> list[ConversationTurn]:
        """Return empty history (Phase 1.5: no multi-turn memory)."""
        logger.debug(
            "MockMemoryStore.get_history called for session=%s (returning [])",
            session_id,
        )
        return []

    async def write_turn(
        self, session_id: str, turn: ConversationTurn
    ) -> None:
        """No-op turn write (Phase 1.5: memory not persisted)."""
        logger.debug(
            "MockMemoryStore.write_turn: session=%s intent=%s [no-op]",
            session_id,
            turn.intent,
        )

    async def delete_session(self, session_id: str) -> None:
        """No-op session delete (Phase 1.5: nothing to delete)."""
        logger.debug(
            "MockMemoryStore.delete_session: session=%s [no-op]", session_id
        )
