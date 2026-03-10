# tests/backend/test_knowledge_adapter.py
"""
Wave 0 stubs for RAG-01 and RAG-02.
Status: PENDING -- stubs are RED (ImportError) or SKIPPED until Plan 01-02 implements the modules.
Per VALIDATION.md: test_bm25_index_builds intentionally fails with ImportError.
"""
import pytest


def test_bm25_index_builds():
    """BM25Okapi index builds from a list of FAQ corpus dicts.
    Fails with ImportError until Plan 01-02 creates backend/app/services/bm25_index.py.
    """
    from backend.app.services.bm25_index import build_bm25_index  # ImportError expected
    corpus = [
        {"text": "property tax due date", "source_doc": "tax.pdf",
         "department": "finance", "chunk_id": "tax.pdf:chunk:0"}
    ]
    bm25, docs = build_bm25_index(corpus)
    assert bm25 is not None
    assert len(docs) == 1


def test_rag_llm_adapter_injects_context():
    """RAGLLMAdapter.generate() returns (text, sources) tuple with non-empty sources.
    Skipped until Plan 01-02 creates backend/app/services/llm.py RAGLLMAdapter class.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")


def test_dynamo_uses_paginator():
    """DynamoKnowledgeAdapter uses boto3 paginator (not raw scan) to load corpus.
    Skipped until Plan 01-02 creates backend/app/services/knowledge.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")


def test_faq_item_has_required_fields():
    """Each FAQ item in DynamoDB corpus has: source_doc, department, chunk_id, text, embedding bytes.
    Skipped until Plan 01-02 creates knowledge/pipeline/ingest.py.
    """
    pytest.skip("Not yet implemented -- Wave 0 stub. Implemented in Plan 01-02.")
