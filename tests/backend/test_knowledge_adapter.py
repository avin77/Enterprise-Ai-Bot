# tests/backend/test_knowledge_adapter.py
"""
Plan 01-02: Knowledge adapter tests -- BM25 index, DynamoDB paginator, RAGLLMAdapter.
"""


def test_bm25_index_builds():
    """BM25Okapi index builds from a list of FAQ corpus dicts."""
    from backend.app.services.bm25_index import build_bm25_index, bm25_search
    corpus = [
        {"text": "property tax due date is october 15", "source_doc": "tax.pdf",
         "department": "finance", "chunk_id": "tax.pdf:chunk:0"},
        {"text": "voter registration deadline is 30 days before election",
         "source_doc": "elections.pdf", "department": "elections", "chunk_id": "elections.pdf:chunk:0"},
    ]
    bm25, docs = build_bm25_index(corpus)
    assert bm25 is not None
    assert len(docs) == 2
    # Verify search works
    results = bm25_search(bm25, docs, "property tax", top_k=1)
    assert len(results) >= 1
    assert results[0]["source_doc"] == "tax.pdf"


def test_rag_llm_adapter_injects_context():
    """RAGLLMAdapter.generate() returns a string response using mock knowledge and mock bedrock."""
    import asyncio
    import unittest.mock as mock
    from backend.app.services.knowledge import MockKnowledgeAdapter
    from backend.app.services.llm import RAGLLMAdapter

    mock_bedrock = mock.MagicMock()
    mock_bedrock.converse.return_value = {
        "output": {"message": {"content": [{"text": "You owe $1,500 in property taxes."}]}}
    }
    adapter = RAGLLMAdapter(
        knowledge_adapter=MockKnowledgeAdapter(),
        bedrock_client=mock_bedrock,
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    )
    result = asyncio.get_event_loop().run_until_complete(adapter.generate("how much do I owe?"))
    assert isinstance(result, str)
    assert len(result) > 0
    # Verify Bedrock was called with system prompt containing FAQ context
    call_kwargs = mock_bedrock.converse.call_args[1]
    assert "system" in call_kwargs, "RAGLLMAdapter must pass system= to Bedrock Converse API"
    assert len(call_kwargs["system"]) > 0
    assert "FAQ" in call_kwargs["system"][0]["text"] or "Jackson County" in call_kwargs["system"][0]["text"]


def test_dynamo_uses_paginator():
    """DynamoKnowledgeAdapter uses boto3 paginator (not raw scan) to load corpus."""
    import inspect
    from backend.app.services.knowledge import DynamoKnowledgeAdapter
    src = inspect.getsource(DynamoKnowledgeAdapter._load_corpus_and_build_index)
    assert "get_paginator" in src, "Must use get_paginator('scan') not dynamo.scan()"
    assert "paginate" in src, "Must call paginator.paginate()"
    # Confirm raw scan() is not used as primary method
    assert "dynamo.scan(" not in src, "Do not use raw dynamo.scan() -- use paginator"


def test_faq_item_has_required_fields():
    """DynamoDB corpus items have the required RAG-01 metadata fields."""
    import asyncio
    from backend.app.services.knowledge import MockKnowledgeAdapter
    adapter = MockKnowledgeAdapter()
    result = asyncio.get_event_loop().run_until_complete(adapter.retrieve("tax", top_k=3))
    assert len(result.chunks) > 0
    assert len(result.sources) == len(result.chunks)
    assert len(result.chunk_ids) == len(result.chunks)
