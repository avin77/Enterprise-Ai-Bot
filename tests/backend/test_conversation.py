# tests/backend/test_conversation.py
"""Tests for ConversationSession and write_conversation_turn (Plan 01-03)."""
import time
import unittest.mock as mock
from dataclasses import dataclass
from backend.app.services.conversation import ConversationSession, write_conversation_turn


@dataclass
class FakePipelineResult:
    asr_ms: float = 200.0
    rag_ms: float = 5.0
    llm_ms: float = 800.0
    tts_ms: float = 400.0


def test_slo_flag_set_on_turn_write():
    """write_conversation_turn sets slo_met=True when total_ms < 1500, False otherwise."""
    mock_dynamo = mock.MagicMock()
    session = ConversationSession()

    # Case 1: total = 200 + 5 + 800 + 400 = 1405ms — under SLO
    fast_result = FakePipelineResult(asr_ms=200.0, rag_ms=5.0, llm_ms=800.0, tts_ms=400.0)
    write_conversation_turn(
        dynamo_client=mock_dynamo,
        session=session,
        user_input="what is my property tax?",
        assistant_response="Your property tax is due October 15.",
        pipeline_result=fast_result,
        rag_chunk_ids=["tax.pdf:chunk:0"],
    )
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_item["slo_met"]["BOOL"] is True, f"Expected slo_met=True for 1405ms, got {call_item['slo_met']}"
    assert call_item["total_ms"]["N"] == "1405.0"

    # Case 2: total = 200 + 5 + 1200 + 400 = 1805ms — exceeds SLO
    slow_result = FakePipelineResult(asr_ms=200.0, rag_ms=5.0, llm_ms=1200.0, tts_ms=400.0)
    write_conversation_turn(
        dynamo_client=mock_dynamo,
        session=session,
        user_input="voter registration deadline?",
        assistant_response="The deadline is 30 days before the election.",
        pipeline_result=slow_result,
    )
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_item["slo_met"]["BOOL"] is False, f"Expected slo_met=False for 1805ms"

    # Case 3: TTL is ~90 days from now
    ttl = int(call_item["ttl"]["N"])
    now = int(time.time())
    assert 89 * 86400 < (ttl - now) <= 91 * 86400, f"TTL not ~90 days: {ttl - now}s"


def test_session_id_format():
    """ConversationSession generates session_id with sess_ prefix."""
    session = ConversationSession()
    assert session.session_id.startswith("sess_"), f"Got: {session.session_id}"
    assert len(session.session_id) == 13, f"Expected 13 chars (sess_ + 8 hex): {session.session_id}"


def test_turn_number_increments():
    """next_turn_number() returns 1, 2, 3... on successive calls."""
    session = ConversationSession()
    assert session.next_turn_number() == 1
    assert session.next_turn_number() == 2
    assert session.next_turn_number() == 3


def test_custom_session_id():
    """ConversationSession accepts a custom session_id."""
    session = ConversationSession(session_id="sess_abc12345")
    assert session.session_id == "sess_abc12345"


def test_write_turn_input_truncation():
    """write_conversation_turn truncates user_input to 2000 chars and response to 4000 chars."""
    mock_dynamo = mock.MagicMock()
    session = ConversationSession()
    long_input = "A" * 3000
    long_response = "B" * 5000

    write_conversation_turn(
        dynamo_client=mock_dynamo,
        session=session,
        user_input=long_input,
        assistant_response=long_response,
        pipeline_result=FakePipelineResult(),
    )
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert len(call_item["user_input"]["S"]) == 2000, "user_input should be truncated to 2000 chars"
    assert len(call_item["assistant_response"]["S"]) == 4000, "response truncated to 4000 chars"


def test_write_turn_rag_chunks_null_when_empty():
    """write_conversation_turn stores rag_chunks_used as NULL when empty/None."""
    mock_dynamo = mock.MagicMock()
    session = ConversationSession()

    write_conversation_turn(
        dynamo_client=mock_dynamo,
        session=session,
        user_input="test",
        assistant_response="response",
        pipeline_result=FakePipelineResult(),
        rag_chunk_ids=None,
    )
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_item["rag_chunks_used"] == {"NULL": True}, \
        f"Expected NULL for empty rag_chunk_ids, got {call_item['rag_chunks_used']}"


def test_write_turn_rag_chunks_string_set():
    """write_conversation_turn stores rag_chunks_used as SS when chunks provided."""
    mock_dynamo = mock.MagicMock()
    session = ConversationSession()

    write_conversation_turn(
        dynamo_client=mock_dynamo,
        session=session,
        user_input="test",
        assistant_response="response",
        pipeline_result=FakePipelineResult(),
        rag_chunk_ids=["chunk:0", "chunk:1"],
    )
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert "SS" in call_item["rag_chunks_used"], \
        f"Expected SS for non-empty rag_chunk_ids, got {call_item['rag_chunks_used']}"
    assert call_item["rag_chunks_used"]["SS"] == ["chunk:0", "chunk:1"]
