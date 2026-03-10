# tests/e2e/test_phase1_roundtrip.py
"""
Wave 0 E2E stub for RAG-01 + RAG-02 + VOIC-03.
Status: PENDING -- skipped until Plans 01-02 and 01-03 are complete.
"""
import pytest


@pytest.mark.asyncio
async def test_full_voice_turn_returns_sources():
    """Full voice turn with mock adapters returns PipelineResult.sources list (non-empty).
    Verifies end-to-end that RAG sources flow from knowledge retrieval through to the result.
    Skipped until Plans 01-02 and 01-03 are complete.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented after Plans 01-02 + 01-03.")
