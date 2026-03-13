"""
RetrievalAgent — wraps Phase 1 BM25 knowledge retrieval.

Phase 1.5: This is a Python class, NOT a Claude call.
Preserves the latency profile of Phase 1 RAG while enabling
agent-based orchestration.

Phase 4 upgrade: Replace retrieve() internals with hybrid BM25 + embeddings
without changing the ChunkResult interface.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from backend.app.services.knowledge import KnowledgeAdapter

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """A single retrieved FAQ chunk with provenance metadata.

    Attributes:
        source_doc: Name/ID of the source document (e.g. 'property-tax-faq.pdf').
        text: The chunk text content.
        score: BM25 retrieval score (higher = more relevant).
        chunk_id: Unique identifier for this chunk in the knowledge store.
    """

    source_doc: str
    text: str
    score: float
    chunk_id: str


class RetrievalAgent:
    """Wraps Phase 1 BM25 retrieval and returns typed ChunkResult objects.

    Parameters
    ----------
    knowledge_adapter:
        KnowledgeAdapter (MockKnowledgeAdapter in dev, DynamoKnowledgeAdapter in prod).
    """

    def __init__(self, knowledge_adapter: KnowledgeAdapter) -> None:
        self._knowledge = knowledge_adapter

    async def retrieve(
        self,
        query: str,
        intent: str = "",
        top_k: int = 3,
    ) -> list[ChunkResult]:
        """Retrieve top-k FAQ chunks for the given query.

        Parameters
        ----------
        query:
            User utterance to search for.
        intent:
            Intent label from OrchestratorAgent. Not used in Phase 1.5 retrieval
            (included for Phase 4 intent-specific synonym expansion).
        top_k:
            Maximum number of chunks to return.

        Returns
        -------
        Ordered list of ChunkResult (highest BM25 score first).
        Returns empty list if no chunks found or on retrieval error.
        """
        try:
            result = await self._knowledge.retrieve(query, top_k=top_k)
        except Exception as exc:
            logger.error(
                "RetrievalAgent: knowledge_adapter.retrieve() failed for query=%r: %s",
                query[:80],
                exc,
            )
            return []

        if not result.chunks:
            logger.debug(
                "RetrievalAgent: no chunks found for query=%r (intent=%s)",
                query[:80],
                intent,
            )
            return []

        chunks = []
        for i, (text, source, chunk_id) in enumerate(
            zip(result.chunks, result.sources, result.chunk_ids)
        ):
            score = result.top_score if i == 0 else 0.0
            chunks.append(
                ChunkResult(
                    source_doc=source,
                    text=text,
                    score=score,
                    chunk_id=chunk_id,
                )
            )

        return chunks
