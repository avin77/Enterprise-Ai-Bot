# tests/knowledge/test_ingest_pipeline.py
import struct
from unittest.mock import MagicMock, patch

from knowledge.pipeline.run_ingest import build_dynamo_item, generate_embedding, _floats_to_bytes


def test_build_dynamo_item_has_required_fields():
    chunk = {
        "text": "County permits require form A12.",
        "source_doc": "permits.pdf",
        "chunk_id": "permits.pdf:chunk:0",
        "department": "planning",
        "page_ref": None,
    }
    embedding = [0.1] * 384
    item = build_dynamo_item(chunk, embedding)
    assert item["chunk_id"]["S"] == "permits.pdf:chunk:0"
    assert item["text"]["S"] == chunk["text"]
    assert item["source_doc"]["S"] == "permits.pdf"
    assert item["department"]["S"] == "planning"
    assert "embedding" in item
    assert "created_at" in item


def test_generate_embedding_returns_384_dims():
    vec = generate_embedding("test sentence about county permits")
    assert len(vec) == 384
    assert all(isinstance(v, float) for v in vec)


def test_floats_to_bytes_roundtrip():
    original = [0.5, -0.3, 1.0] + [0.0] * 381
    packed = _floats_to_bytes(original)
    unpacked = list(struct.unpack(f"<{len(original)}f", packed))
    assert abs(unpacked[0] - 0.5) < 1e-5
    assert abs(unpacked[1] - -0.3) < 1e-5
