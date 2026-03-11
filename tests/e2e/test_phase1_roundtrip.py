# tests/e2e/test_phase1_roundtrip.py
"""
Plan 01-02: E2E test for full voice turn with RAG sources flowing through pipeline.
"""
import pytest


@pytest.mark.asyncio
async def test_full_voice_turn_returns_sources():
    """Full voice turn with mock adapters returns PipelineResult.sources list (non-empty).
    Verifies end-to-end that RAG sources flow from knowledge retrieval through to the result.
    """
    from backend.app.orchestrator.runtime import build_pipeline
    pipeline = build_pipeline()
    result = await pipeline.run_roundtrip(b"fake-audio-bytes")
    # With MockKnowledgeAdapter, sources must be non-empty (sample_faqs.json loaded)
    assert hasattr(result, "sources"), "PipelineResult missing sources field"
    assert isinstance(result.sources, list)
    assert len(result.sources) > 0, "Sources list empty -- RAG not wired into pipeline"
    for source in result.sources:
        assert source, f"Empty source in sources list: {result.sources}"
