# backend/app/services/redis_cache.py
"""
BM25RedisRetriever: Redis query result cache with transparent BM25 fallback.

Critical invariant: voice turns must NEVER fail due to Redis unavailability.
Redis is an optimization (1ms cache hit), not a dependency.
On any Redis error: log warning, fall through to BM25 silently.

Cache design:
- Key: "bm25:v1:{SHA-256 of normalized query[:16]}"
- Value: JSON-serialized list[dict] with text, source_doc, chunk_id, score fields
- TTL: 3600 seconds (1 hour -- FAQ content refreshes monthly)
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None  # type: ignore

from backend.app.services.bm25_index import BM25Okapi, bm25_search

logger = logging.getLogger(__name__)


class BM25RedisRetriever:
    """
    BM25 retrieval with Redis query result cache and transparent fallback.
    Cache miss or Redis error: run BM25 directly. NEVER propagate Redis errors.
    """

    CACHE_PREFIX = "bm25:v1:"
    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        bm25_index: BM25Okapi,
        corpus: list[dict],
        redis_url: Optional[str] = None,
        redis_ttl: int = DEFAULT_TTL,
    ) -> None:
        self._bm25 = bm25_index
        self._corpus = corpus
        self._redis_ttl = redis_ttl
        self._redis: Optional[object] = None

        if redis_url and redis_lib is not None:
            try:
                pool = redis_lib.ConnectionPool.from_url(redis_url, decode_responses=True)
                self._redis = redis_lib.Redis(connection_pool=pool)
                # Test connection at startup -- if Redis is down, set to None
                self._redis.ping()
            except Exception as exc:
                logger.warning("Redis unavailable at startup (%s) -- using direct BM25", exc)
                self._redis = None

    def _cache_key(self, query: str) -> str:
        normalized = query.lower().strip()
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{self.CACHE_PREFIX}{digest}"

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Returns top_k FAQ results. NEVER raises due to Redis failure.

        Flow:
        1. Try Redis GET (cache hit: return immediately)
        2. Cache miss or Redis error: run BM25 with query expansion
        3. Try Redis SET to populate cache (fire-and-forget, ignore errors)
        4. Return BM25 results
        """
        cache_key = self._cache_key(query)

        # Step 1-2: Try cache
        if self._redis is not None:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                # Redis down during request -- NEVER propagate
                logger.warning("Redis GET failed (%s) -- falling back to BM25", exc)

        # Step 3: BM25 retrieval (query expansion applied inside bm25_search)
        results = bm25_search(self._bm25, self._corpus, query, top_k=top_k)

        # Step 4: Populate cache (fire-and-forget)
        if self._redis is not None and results:
            try:
                self._redis.setex(cache_key, self._redis_ttl, json.dumps(results))
            except Exception as exc:
                logger.warning("Redis SET failed (%s) -- result still returned", exc)

        return results
