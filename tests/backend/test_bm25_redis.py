# tests/backend/test_bm25_redis.py
"""
Plan 01-02: BM25 + Redis retrieval tests.
"""


def test_redis_fallback_on_failure():
    """BM25RedisRetriever.search() returns BM25 results when Redis raises ConnectionError.
    Voice turns must NEVER fail due to Redis outage -- fallback is critical.
    """
    import unittest.mock as mock
    from rank_bm25 import BM25Okapi
    from backend.app.services.redis_cache import BM25RedisRetriever

    corpus = [
        {"text": "property tax payment due october", "source_doc": "tax.pdf",
         "chunk_id": "tax.pdf:chunk:0"},
    ]
    bm25 = BM25Okapi([c["text"].lower().split() for c in corpus])

    # Simulate Redis that raises ConnectionError on every call
    broken_redis = mock.MagicMock()
    broken_redis.ping.side_effect = Exception("Connection refused")

    retriever = BM25RedisRetriever(bm25_index=bm25, corpus=corpus, redis_url=None)
    retriever._redis = broken_redis
    broken_redis.get.side_effect = Exception("Connection refused")

    # Must return BM25 results even with broken Redis -- NEVER raise
    results = retriever.search("property tax", top_k=1)
    assert len(results) >= 1, "Should return BM25 results despite Redis failure"
    assert results[0]["source_doc"] == "tax.pdf"


def test_expand_government_query_adds_synonyms():
    """expand_government_query('trash') expands to include at least one synonym.
    Full synonym dict must have >=30 base term keys.
    """
    from backend.app.services.bm25_index import expand_government_query, GOVERNMENT_SYNONYMS
    # Must have >=30 base terms
    assert len(GOVERNMENT_SYNONYMS) >= 30, f"Only {len(GOVERNMENT_SYNONYMS)} synonym keys -- need >=30"
    # Expansion must add terms
    result = expand_government_query("trash")
    assert "garbage" in result or "waste" in result, f"No synonyms added for 'trash': {result}"
    # Unknown terms should pass through unchanged
    unmodified = expand_government_query("hello world")
    assert unmodified == "hello world"


def test_retrieve_returns_source_attribution():
    """BM25RedisRetriever results include source_doc field on every returned item."""
    import asyncio
    from backend.app.services.knowledge import MockKnowledgeAdapter

    adapter = MockKnowledgeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        adapter.retrieve("property tax", top_k=3)
    )
    assert len(result.sources) > 0
    for source in result.sources:
        assert source, f"Empty source_doc found in result: {result}"
