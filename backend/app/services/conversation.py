# backend/app/services/conversation.py
"""
Conversation session tracking for Phase 1.
Writes per-turn records to DynamoDB voicebot-conversations table with TTL.
Provides session_id, turn_number, per-stage timing, slo_met flag.

Table schema:
PK: session_id (S) — "sess_{8-char uuid hex}"
SK: turn_number (N) — integer 1, 2, 3...
TTL: ttl (N) — Unix epoch + 90 days (DynamoDB auto-expires after 90 days)

Conversation tracking is NOT done inside VoicePipeline — it's done in the WebSocket handler
(main.py) after the pipeline result is returned. This keeps pipeline.py pure (no side effects)
and testable without DynamoDB.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional


class ConversationSession:
    """Lightweight conversation tracker. One instance per WebSocket connection."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        self.turn_number = 0

    def next_turn_number(self) -> int:
        """Increment and return turn number. First call returns 1."""
        self.turn_number += 1
        return self.turn_number


def write_conversation_turn(
    dynamo_client,
    session: ConversationSession,
    user_input: str,
    assistant_response: str,
    pipeline_result,  # PipelineResult with asr_ms, rag_ms, llm_ms, tts_ms fields
    rag_chunk_ids: Optional[list[str]] = None,
    table_name: str = "voicebot-conversations",
) -> None:
    """
    Write a single conversation turn to DynamoDB.

    slo_met: True when total_ms < 1500 (Phase 1 SLO target).
    TTL: 90 days from now (DynamoDB auto-deletes expired items).
    Truncation: user_input[:2000], assistant_response[:4000] to stay within item size limits.
    """
    now = datetime.now(timezone.utc)
    ttl_90_days = int(now.timestamp()) + (90 * 86400)

    total_ms = (
        getattr(pipeline_result, "asr_ms", 0.0)
        + getattr(pipeline_result, "rag_ms", 0.0)
        + getattr(pipeline_result, "llm_ms", 0.0)
        + getattr(pipeline_result, "tts_ms", 0.0)
    )

    item = {
        "session_id":         {"S": session.session_id},
        "turn_number":        {"N": str(session.next_turn_number())},
        "user_input":         {"S": user_input[:2000]},
        "assistant_response": {"S": assistant_response[:4000]},
        "asr_ms":             {"N": str(round(getattr(pipeline_result, "asr_ms", 0.0), 2))},
        "rag_ms":             {"N": str(round(getattr(pipeline_result, "rag_ms", 0.0), 2))},
        "llm_ms":             {"N": str(round(getattr(pipeline_result, "llm_ms", 0.0), 2))},
        "tts_ms":             {"N": str(round(getattr(pipeline_result, "tts_ms", 0.0), 2))},
        "total_ms":           {"N": str(round(total_ms, 2))},
        "timestamp":          {"S": now.isoformat()},
        "slo_met":            {"BOOL": total_ms < 1500},
        "ttl":                {"N": str(ttl_90_days)},
    }

    # rag_chunks_used: DynamoDB StringSet (SS) if non-empty, NULL otherwise
    if rag_chunk_ids:
        item["rag_chunks_used"] = {"SS": rag_chunk_ids}
    else:
        item["rag_chunks_used"] = {"NULL": True}

    dynamo_client.put_item(TableName=table_name, Item=item)
