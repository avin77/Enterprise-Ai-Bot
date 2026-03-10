# tests/backend/test_latency_probes.py
"""
Wave 0 stubs for VOIC-03 (per-stage pipeline timing).
Status: PENDING -- skipped until Plan 01-02 adds timing fields to PipelineResult.
"""
import pytest


def test_pipeline_result_has_timing_fields():
    """PipelineResult has asr_ms, rag_ms, llm_ms, tts_ms float fields.
    These are added to PipelineResult in Plan 01-02 (pipeline.py modification).
    Skipped until Plan 01-02 modifies backend/app/orchestrator/pipeline.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")
