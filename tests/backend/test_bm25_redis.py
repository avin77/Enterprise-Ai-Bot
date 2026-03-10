# tests/backend/test_bm25_redis.py
"""
Wave 0 stubs for RAG-02 (BM25 + Redis).
Status: PENDING -- all skipped until Plan 01-02 implements the modules.
"""
import pytest


def test_redis_fallback_on_failure():
    """BM25RedisRetriever.search() returns BM25 results when Redis raises ConnectionError.
    Voice turns must NEVER fail due to Redis outage -- fallback is critical.
    Skipped until Plan 01-02 creates backend/app/services/redis_cache.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")


def test_expand_government_query_adds_synonyms():
    """expand_government_query('trash') expands to include at least one synonym.
    Full synonym dict must have >=30 base term keys.
    Skipped until Plan 01-02 creates backend/app/services/bm25_index.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")


def test_retrieve_returns_source_attribution():
    """BM25RedisRetriever results include source_doc field on every returned item.
    Skipped until Plan 01-02 implements retriever.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")
