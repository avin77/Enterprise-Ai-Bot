# backend/app/services/knowledge.py
"""
KnowledgeAdapter: ABC + MockKnowledgeAdapter (JSON) + DynamoKnowledgeAdapter (DynamoDB + BM25 + Redis).

Stack: DynamoDB (corpus store) + BM25 (rank_bm25 retrieval) + Redis (cache with fallback).
NO pgvector. NO Aurora PostgreSQL. All-MiniLM-L6-v2 embeddings stored in DynamoDB Binary
but NOT used for BM25 queries -- reserved for Phase 4 hybrid upgrade.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    chunks: list[str]                  # Top-k FAQ text chunks
    sources: list[str]                 # Source document names for citation (RAG-02 Phase 1)
    chunk_ids: list[str]               # chunk_id for DynamoDB reference
    search_latency_ms: float
    redis_hit: bool = False            # True if result came from Redis cache
    top_score: float = 0.0            # BM25 top-1 score (proxy for RAG quality)
    page_ref: str | None = None        # RAG-02: top-result page/section ref (None for Phase 1; Phase 4 populates)
    page_refs: list[Optional[str]] = field(default_factory=list)
    # page_ref: singular top-result citation field. None for all Phase 1 entries.
    # page_refs: parallel to sources list. None for Phase 1 (page/section added in Phase 4).
    # Both pre-provisioned so Phase 4 can populate without a schema migration.


class KnowledgeAdapter(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 3) -> KnowledgeResult:
        raise NotImplementedError


class MockKnowledgeAdapter(KnowledgeAdapter):
    """Offline dev: loads sample_faqs.json and runs BM25 over it. Returns top_k entries."""

    def __init__(self, faq_path: Optional[str] = None) -> None:
        default = Path(__file__).parent.parent.parent.parent / "knowledge/data/local/sample_faqs.json"
        path = Path(faq_path) if faq_path else default
        with path.open() as f:
            self._faqs = json.load(f)
        # Build BM25 index over FAQ answers for offline retrieval
        from backend.app.services.bm25_index import build_bm25_index, bm25_search
        self._bm25, self._docs = build_bm25_index([
            {
                "text": e["answer"],
                "source_doc": e["source_doc"],
                "chunk_id": e.get("chunk_id", f"chunk:{i}"),
                "page_ref": e.get("page_ref"),
            }
            for i, e in enumerate(self._faqs)
        ])
        self._bm25_search = bm25_search

    async def retrieve(self, query: str, top_k: int = 3) -> KnowledgeResult:
        t0 = time.monotonic()
        results = self._bm25_search(self._bm25, self._docs, query, top_k=top_k)
        latency = max((time.monotonic() - t0) * 1000, 0.1)

        if not results:
            # Fallback: return first top_k FAQ entries if no BM25 match
            selected = self._faqs[:top_k]
            return KnowledgeResult(
                chunks=[e["answer"] for e in selected],
                sources=[e["source_doc"] for e in selected],
                chunk_ids=[e.get("chunk_id", f"chunk:{i}") for i, e in enumerate(selected)],
                search_latency_ms=latency,
                redis_hit=False,
                top_score=0.0,
                page_refs=[e.get("page_ref") for e in selected],
            )

        return KnowledgeResult(
            chunks=[r["text"] for r in results],
            sources=[r["source_doc"] for r in results],
            chunk_ids=[r["chunk_id"] for r in results],
            search_latency_ms=latency,
            redis_hit=False,
            top_score=results[0]["score"] if results else 0.0,
            page_refs=[r.get("page_ref") for r in results],
        )


class DynamoKnowledgeAdapter(KnowledgeAdapter):
    """
    Production: loads FAQ corpus from DynamoDB at startup, builds BM25 index in-memory.
    Query: BM25RedisRetriever (Redis cache + BM25 fallback).

    Important: embeddings stored in DynamoDB Binary are loaded but NOT used for BM25 retrieval.
    They are stored for Phase 4 hybrid search upgrade. Do not load embedding bytes into BM25 index.
    """

    def __init__(
        self,
        table_name: str,
        region: str = "ap-south-1",
        redis_url: Optional[str] = None,
    ) -> None:
        self._table_name = table_name
        self._region = region
        self._redis_url = redis_url
        self._retriever: Optional[object] = None  # lazy init on first retrieve()
        self._corpus: list[dict] = []

    def _load_corpus_and_build_index(self) -> None:
        """
        Scan DynamoDB table using paginator (handles >1MB responses correctly).
        Build BM25 index in-memory. Call once at startup via FastAPI lifespan.

        IMPORTANT: Use get_paginator("scan") -- NOT the raw scan method directly.
        The raw scan method silently truncates at 1MB (LastEvaluatedKey pagination not handled).
        """
        import boto3
        from backend.app.services.bm25_index import build_bm25_index
        from backend.app.services.redis_cache import BM25RedisRetriever

        dynamo = boto3.client("dynamodb", region_name=self._region)
        paginator = dynamo.get_paginator("scan")

        corpus = []
        for page in paginator.paginate(TableName=self._table_name):
            for item in page["Items"]:
                corpus.append({
                    "text": item["text"]["S"],
                    "source_doc": item["source_doc"]["S"],
                    "department": item["department"]["S"],
                    "chunk_id": item["chunk_id"]["S"],
                    "page_ref": item.get("page_ref", {}).get("S"),  # None if not set
                    # Note: "embedding" (B) is present in DynamoDB but intentionally NOT loaded here.
                    # BM25 does not use embeddings. Phase 4 hybrid upgrade will load them.
                })

        if not corpus:
            raise ValueError(
                f"DynamoDB table '{self._table_name}' returned zero items. "
                "Run the ingest pipeline first: python knowledge/pipeline/ingest.py"
            )

        bm25, docs = build_bm25_index(corpus)
        self._corpus = docs
        self._retriever = BM25RedisRetriever(
            bm25_index=bm25,
            corpus=docs,
            redis_url=self._redis_url,
        )
        logger.info(
            "DynamoKnowledgeAdapter: loaded %d FAQ chunks, BM25 index built. "
            "Redis: %s",
            len(corpus),
            "connected" if self._retriever._redis else "unavailable (direct BM25)",
        )

    async def retrieve(self, query: str, top_k: int = 3) -> KnowledgeResult:
        import asyncio
        if self._retriever is None:
            # Lazy init: load corpus on first retrieve call
            # In production use FastAPI lifespan to call this at startup
            await asyncio.to_thread(self._load_corpus_and_build_index)

        t0 = time.monotonic()
        results = await asyncio.to_thread(self._retriever.search, query, top_k)
        latency = (time.monotonic() - t0) * 1000

        if not results:
            # No matching FAQs found -- return empty result (caller handles gracefully)
            return KnowledgeResult(
                chunks=[], sources=[], chunk_ids=[],
                search_latency_ms=latency, redis_hit=False, top_score=0.0,
                page_refs=[],
            )

        return KnowledgeResult(
            chunks=[r["text"] for r in results],
            sources=[r["source_doc"] for r in results],
            chunk_ids=[r["chunk_id"] for r in results],
            search_latency_ms=latency,
            redis_hit=False,  # BM25RedisRetriever tracks this internally; expose in Phase 4
            top_score=results[0]["score"] if results else 0.0,
            page_refs=[r.get("page_ref") for r in results],  # None for Phase 1 entries
        )
