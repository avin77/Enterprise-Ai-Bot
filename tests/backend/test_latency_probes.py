# tests/backend/test_latency_probes.py
"""
Plan 01-02: Per-stage pipeline timing fields test (VOIC-03).
Plan 01-04: LatencyBuffer and publish_turn_metrics unit tests.
"""
import asyncio


def test_pipeline_result_has_timing_fields():
    """PipelineResult has asr_ms, rag_ms, llm_ms, tts_ms float fields.
    These are added to PipelineResult in Plan 01-02 (pipeline.py modification).
    """
    from backend.app.orchestrator.runtime import build_pipeline
    pipeline = build_pipeline()
    result = asyncio.run(pipeline.run_roundtrip(b"fake-audio"))
    assert hasattr(result, "asr_ms"), "PipelineResult missing asr_ms field"
    assert hasattr(result, "rag_ms"), "PipelineResult missing rag_ms field"
    assert hasattr(result, "llm_ms"), "PipelineResult missing llm_ms field"
    assert hasattr(result, "tts_ms"), "PipelineResult missing tts_ms field"
    # All timing fields must be positive (not zero -- zero means instrumentation broken)
    total = result.asr_ms + result.rag_ms + result.llm_ms + result.tts_ms
    assert total > 0.0, f"All timing fields zero -- instrumentation broken. Result: {result}"


def test_publish_turn_metrics_no_op_when_mock():
    """publish_turn_metrics is a no-op for CloudWatch when USE_AWS_MOCKS=true."""
    import os
    import unittest.mock as mock
    from backend.app.monitoring import publish_turn_metrics
    os.environ["USE_AWS_MOCKS"] = "true"
    mock_cw = mock.MagicMock()
    fake_result = type("R", (), {"asr_ms": 200.0, "rag_ms": 5.0, "llm_ms": 800.0, "tts_ms": 400.0})()
    publish_turn_metrics(fake_result, False, 1.5, False, mock_cw)
    mock_cw.put_metric_data.assert_not_called()


def test_publish_turn_metrics_no_op_when_cw_client_none():
    """publish_turn_metrics does not raise when cw_client=None."""
    import os
    from backend.app.monitoring import publish_turn_metrics
    os.environ["USE_AWS_MOCKS"] = "false"
    fake_result = type("R", (), {"asr_ms": 10.0, "rag_ms": 5.0, "llm_ms": 100.0, "tts_ms": 50.0})()
    # Must not raise even when cw_client=None
    publish_turn_metrics(fake_result, False, 0.5, False, cw_client=None)
    # Restore default
    os.environ["USE_AWS_MOCKS"] = "true"


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
    """LatencyBuffer.percentiles returns zeros when buffer is empty."""
    from backend.app.monitoring import LatencyBuffer
    buf = LatencyBuffer()
    pcts = buf.percentiles("asr")
    assert pcts == {"p50": 0.0, "p95": 0.0, "p99": 0.0}


def test_get_latency_buffer_returns_singleton():
    """get_latency_buffer() returns the module-level singleton."""
    from backend.app.monitoring import get_latency_buffer, LatencyBuffer
    buf1 = get_latency_buffer()
    buf2 = get_latency_buffer()
    assert buf1 is buf2, "get_latency_buffer() should return the same singleton instance"
    assert isinstance(buf1, LatencyBuffer)
