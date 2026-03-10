# tests/backend/test_monitoring.py
"""
Phase 1 Plan 04: CloudWatch monitoring unit tests.
Tests LatencyBuffer, publish_turn_metrics, and get_latency_buffer singleton.
"""
import os
import unittest.mock as mock

import pytest


def test_publish_turn_metrics_no_op_when_mock():
    """publish_turn_metrics is a no-op when USE_AWS_MOCKS=true."""
    os.environ["USE_AWS_MOCKS"] = "true"
    from backend.app.monitoring import publish_turn_metrics

    mock_cw = mock.MagicMock()
    fake_result = type(
        "R",
        (),
        {"asr_ms": 200.0, "rag_ms": 5.0, "llm_ms": 800.0, "tts_ms": 400.0},
    )()
    publish_turn_metrics(fake_result, False, 1.5, False, mock_cw)
    mock_cw.put_metric_data.assert_not_called()


def test_latency_buffer_percentiles_correct():
    """LatencyBuffer.percentiles on 100 values returns correct p50/p95/p99."""
    from backend.app.monitoring import LatencyBuffer

    buf = LatencyBuffer()

    class FakeResult:
        pass

    for i in range(1, 101):  # values 1.0 to 100.0
        r = FakeResult()
        r.asr_ms = float(i)
        r.rag_ms = 0.0
        r.llm_ms = 0.0
        r.tts_ms = 0.0
        buf.record(r)
    pcts = buf.percentiles("asr")
    assert 48 <= pcts["p50"] <= 52, f"p50 wrong: {pcts['p50']}"
    assert 93 <= pcts["p95"] <= 97, f"p95 wrong: {pcts['p95']}"
    assert 98 <= pcts["p99"] <= 100, f"p99 wrong: {pcts['p99']}"


def test_latency_buffer_empty_returns_zeros():
    """Empty LatencyBuffer returns zeros for all percentiles."""
    from backend.app.monitoring import LatencyBuffer

    buf = LatencyBuffer()
    pcts = buf.percentiles("rag")
    assert pcts["p50"] == 0.0
    assert pcts["p95"] == 0.0
    assert pcts["p99"] == 0.0


def test_all_percentiles_has_all_stages():
    """all_percentiles() returns dict with asr, rag, llm, tts keys."""
    from backend.app.monitoring import LatencyBuffer

    buf = LatencyBuffer()
    result = buf.all_percentiles()
    for stage in ("asr", "rag", "llm", "tts"):
        assert stage in result, f"Stage {stage} missing from all_percentiles"
        assert "p50" in result[stage]
        assert "p95" in result[stage]
        assert "p99" in result[stage]


def test_get_latency_buffer_returns_singleton():
    """get_latency_buffer() returns the same singleton instance each call."""
    from backend.app.monitoring import get_latency_buffer

    buf1 = get_latency_buffer()
    buf2 = get_latency_buffer()
    assert buf1 is buf2


def test_publish_turn_metrics_never_raises():
    """publish_turn_metrics does not propagate CloudWatch exceptions."""
    os.environ["USE_AWS_MOCKS"] = "false"
    try:
        import importlib

        import backend.app.monitoring as mon_mod

        importlib.reload(mon_mod)
        ptm = mon_mod.publish_turn_metrics

        mock_cw = mock.MagicMock()
        mock_cw.put_metric_data.side_effect = RuntimeError("CW unavailable")
        fake_result = type(
            "R",
            (),
            {"asr_ms": 200.0, "rag_ms": 5.0, "llm_ms": 800.0, "tts_ms": 400.0},
        )()
        # Must not raise
        ptm(fake_result, False, 1.5, False, mock_cw, env="dev")
    finally:
        os.environ["USE_AWS_MOCKS"] = "true"


def test_latency_buffer_invalid_stage_raises():
    """percentiles() with unknown stage raises ValueError."""
    from backend.app.monitoring import LatencyBuffer

    buf = LatencyBuffer()
    with pytest.raises(ValueError, match="Unknown stage"):
        buf.percentiles("unknown_stage")


def test_latency_buffer_rolling_window():
    """LatencyBuffer with maxlen=10 evicts old entries."""
    from backend.app.monitoring import LatencyBuffer

    buf = LatencyBuffer(maxlen=10)

    class FakeResult:
        rag_ms = 0.0
        llm_ms = 0.0
        tts_ms = 0.0

    for i in range(20):
        r = FakeResult()
        r.asr_ms = float(i)
        buf.record(r)

    # After 20 inserts into maxlen=10, only last 10 values remain (10.0-19.0)
    data = sorted(buf._data["asr"])
    assert len(data) == 10
    assert min(data) >= 10.0
