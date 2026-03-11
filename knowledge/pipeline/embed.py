# knowledge/pipeline/embed.py
"""
Embedding generation (all-MiniLM-L6-v2, 384-dim) and DynamoDB storage.
Embeddings stored as DynamoDB Binary (type B) for Phase 4 hybrid search.
NOT used for BM25 retrieval in Phase 1 -- stored only for future upgrade readiness.

LAZY IMPORT: sentence_transformers is imported only inside load_embedding_model().
Do NOT add 'from sentence_transformers import ...' at module level.
This keeps BM25-only code paths free of the ~91MB PyTorch model load overhead.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np


def load_embedding_model():
    """
    Load sentence-transformers all-MiniLM-L6-v2 (384-dim, ~91MB, CPU-capable).

    LAZY IMPORT: sentence_transformers imported here (inside function body), NOT at module level.
    This prevents the ~91MB model from loading when bm25_index.py or redis_cache.py are imported.
    Call this function only from the ingest pipeline (knowledge/scripts/), never from hot path.
    """
    from sentence_transformers import SentenceTransformer  # lazy -- intentional
    return SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding(model, text: str) -> bytes:
    """
    Generate 384-dim float32 embedding and convert to bytes for DynamoDB Binary storage.
    boto3 handles base64 encoding transparently. Pass raw bytes.

    Args:
        model: SentenceTransformer model (loaded via load_embedding_model())
        text: text to embed

    Returns:
        1536 bytes (384 * 4 bytes, float32 little-endian)
    """
    embedding = model.encode(text, convert_to_numpy=True).astype(np.float32)
    assert embedding.shape == (384,), f"Expected 384-dim, got {embedding.shape}"
    return embedding.tobytes()  # 1536 bytes (384 * 4)


def embed_and_store_chunks(
    chunks: list[dict],
    model,
    dynamo_client,
    table_name: str = "voicebot-faq-knowledge",
) -> int:
    """
    Embed each chunk with all-MiniLM-L6-v2 and write to DynamoDB.
    Uses DynamoDB PK=department, SK=chunk_id schema.

    Args:
        chunks: list of dicts from extract_chunks_from_pdf()
        model: loaded SentenceTransformer model
        dynamo_client: boto3 DynamoDB client
        table_name: DynamoDB table name

    Returns:
        count of items stored
    """
    stored = 0
    now = datetime.now(timezone.utc).isoformat()

    for chunk in chunks:
        embedding_bytes = generate_embedding(model, chunk["text"])
        item = {
            "department":  {"S": chunk["department"]},
            "chunk_id":    {"S": chunk["chunk_id"]},
            "text":        {"S": chunk["text"][:4000]},  # DynamoDB item limit guard
            "source_doc":  {"S": chunk["source_doc"]},
            "embedding":   {"B": embedding_bytes},  # 384-dim float32 as bytes
            "created_at":  {"S": now},
        }
        # page_ref stored as String if present, omitted if None (Phase 1: always None)
        if chunk.get("page_ref") is not None:
            item["page_ref"] = {"S": chunk["page_ref"]}
        dynamo_client.put_item(TableName=table_name, Item=item)
        stored += 1

    return stored
