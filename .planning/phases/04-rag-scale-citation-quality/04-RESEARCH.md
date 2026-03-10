# Phase 4: RAG Scale + Citation Quality — Research

**Researched:** 2026-03-10
**Domain:** PDF parsing, hybrid BM25+embedding retrieval, DynamoDB at scale, citation quality
**Confidence:** HIGH (BM25 + embedding re-rank is well-established; pdfplumber latency benchmarked)

---

## Standard Stack

| Component | Library |
|-----------|---------|
| PDF parsing | `pdfplumber` (tables + text) |
| Chunking | `langchain_text_splitters.RecursiveCharacterTextSplitter` |
| BM25 (existing) | `rank_bm25.BM25Okapi` |
| Embedding re-ranker | `sentence-transformers` `all-MiniLM-L6-v2` (already in Phase 1) |
| Score logging | DynamoDB per-retrieval record |
| BM25 index caching | S3 pickle file (loaded at container startup) |

---

## Architecture: Hybrid Retrieval

```
Query (with synonym expansion)
    ↓
BM25 search → top-20 candidates
    ↓
Load embeddings for 20 candidates from DynamoDB (BatchGetItem)
    ↓
Compute cosine similarity: query_embedding vs each candidate embedding
    ↓
Fused score: 0.4 × BM25_norm + 0.6 × cosine_sim
    ↓
Return top-3 by fused score
    ↓
Log all 20 candidate scores to CloudWatch Logs
```

### Score Fusion Formula

```python
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def hybrid_retrieve(query: str, bm25_candidates: list[ScoredChunk], top_k: int = 3) -> list[ScoredChunk]:
    query_embedding = model.encode(query, normalize_embeddings=True)

    # Normalize BM25 scores to [0,1]
    bm25_scores = np.array([c.bm25_score for c in bm25_candidates])
    bm25_norm = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-9)

    # Load embeddings from DynamoDB (BatchGetItem for all 20)
    chunk_ids = [c.chunk_id for c in bm25_candidates]
    embeddings = batch_get_embeddings(chunk_ids)  # returns {chunk_id: np.array}

    fused_scores = []
    for i, candidate in enumerate(bm25_candidates):
        emb = embeddings[candidate.chunk_id]
        cosine_sim = float(np.dot(query_embedding, emb))  # both normalized → cosine = dot product
        fused = 0.4 * bm25_norm[i] + 0.6 * cosine_sim
        fused_scores.append({
            "chunk_id": candidate.chunk_id,
            "bm25_score": float(bm25_scores[i]),
            "bm25_score_norm": float(bm25_norm[i]),
            "cosine_sim": cosine_sim,
            "fused_score": fused,
        })
        log_candidate_score(fused_scores[-1])  # fire-and-forget

    fused_scores.sort(key=lambda x: x["fused_score"], reverse=True)
    return [bm25_candidates[fused_scores.index(s)] for s in fused_scores[:top_k]]
```

**Weight choice (0.4 BM25 + 0.6 cosine):** Empirically favors semantic similarity for government FAQ queries. Tune after collecting Phase 4 retrieval logs.

### Batch Embedding Fetch from DynamoDB

```python
def batch_get_embeddings(chunk_ids: list[str]) -> dict[str, np.ndarray]:
    """Fetch pre-computed embeddings from DynamoDB. ~5ms for 20 items."""
    response = dynamodb.batch_get_item(
        RequestItems={
            "voicebot_knowledge": {
                "Keys": [{"chunk_id": {"S": cid}} for cid in chunk_ids],
                "ProjectionExpression": "chunk_id, embedding",
            }
        }
    )
    result = {}
    for item in response["Responses"]["voicebot_knowledge"]:
        cid = item["chunk_id"]["S"]
        embedding_bytes = item["embedding"]["B"]
        result[cid] = np.frombuffer(embedding_bytes, dtype=np.float32)
    return result
```

---

## PDF Parsing

**Library: `pdfplumber`** — Best for government PDFs with mixed text + tables. pypdf2 misses table structure. LlamaParse is API-based (adds latency, cost, network dependency).

```python
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Returns list of {page_num, text, tables} dicts."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            # Convert tables to markdown for better BM25 indexing
            table_text = "\n".join(
                " | ".join(str(cell) for cell in row)
                for table in tables for row in table
            )
            pages.append({
                "page_num": i + 1,
                "text": text + "\n" + table_text,
                "source_doc": Path(pdf_path).name,
            })
    return pages
```

### Chunking Strategy

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,       # tokens (approx 400 words)
    chunk_overlap=50,     # tokens overlap
    separators=["\n\n", "\n", ". ", " "],
)

def chunk_page(page: dict) -> list[dict]:
    chunks = splitter.split_text(page["text"])
    return [
        {
            "chunk_id": f"{page['source_doc']}-p{page['page_num']}-c{i}",
            "text": chunk,
            "source_doc": page["source_doc"],
            "page_num": page["page_num"],
            "chunk_index": i,
            "section": extract_section_header(chunk),  # heuristic: first line if title-case
        }
        for i, chunk in enumerate(chunks)
    ]
```

### DynamoDB Chunk Record (updated for Phase 4)

```python
{
    "chunk_id": "jackson-utilities-guide-p3-c2",  # PK
    "department": "utilities",                      # for GSI filtering
    "text": str,
    "source_doc": str,
    "page_num": int,
    "section": str,
    "chunk_index": int,
    "embedding": bytes,                             # 384-dim float32 = 1,536 bytes
    "created_at": str,                              # ISO 8601
    "tags": list[str],                              # e.g. ["water", "billing", "payment"]
}
```

---

## BM25 Index Scaling

**At Phase 4 scale:** 20 docs × ~100 chunks = 2,000 chunks. In-memory BM25 index = ~5MB. Fine.

**Scaling limit:** In-memory BM25 becomes problematic at ~50,000 chunks (~250MB). At that point, store index as gzip pickle in S3 and load at container startup.

**S3 pickle for Phase 4:**
```python
import pickle, gzip, boto3

def save_bm25_index(corpus: list[str], s3_key: str) -> None:
    bm25 = BM25Okapi([doc.split() for doc in corpus])
    payload = gzip.compress(pickle.dumps(bm25))
    boto3.client("s3").put_object(Bucket="voice-bot-knowledge", Key=s3_key, Body=payload)

def load_bm25_index(s3_key: str) -> BM25Okapi:
    obj = boto3.client("s3").get_object(Bucket="voice-bot-knowledge", Key=s3_key)
    return pickle.loads(gzip.decompress(obj["Body"].read()))
```

DynamoDB Scan for 2,000 chunks at startup: ~200 RCUs = $0.05 per cold start. Acceptable.

---

## Citation Quality

### Page/Section Attribution in Voice

```python
def format_citation_for_voice(chunk: ChunkResult) -> str:
    """Natural language citation suitable for TTS."""
    doc_name = chunk.source_doc.replace("-", " ").replace(".pdf", "").title()
    if chunk.section:
        return f"According to the {doc_name}, {chunk.section} section"
    elif chunk.page_num:
        return f"According to the {doc_name}"
    else:
        return f"According to Jackson County records"
```

### Citation Precision Eval (LLM-as-judge)

```python
CITATION_JUDGE = """
User query: {query}
Bot response: {response}
Source chunk the bot cited: {cited_chunk_text}

Is the source chunk actually relevant to answering the user's query? A relevant chunk:
- Contains information that directly answers the query
- Is from the correct department/topic area
- Is not tangentially related

Respond with only: RELEVANT or IRRELEVANT
"""
```

---

## Query Expansion Paraphrase Tests

Test that synonym-expanded queries retrieve the same chunks:
```python
PARAPHRASE_PAIRS = [
    ("trash pickup schedule", "waste collection garbage"),
    ("water bill payment", "utility payment balance"),
    ("building permit application", "construction license permit"),
    ("SNAP benefits", "food stamps EBT assistance"),
    ("property tax assessment", "real estate tax appraisal"),
]

def test_paraphrase_recall():
    for original, paraphrase in PARAPHRASE_PAIRS:
        original_chunks = retrieve(original)
        paraphrase_chunks = retrieve(paraphrase)
        overlap = len(set(c.chunk_id for c in original_chunks) &
                     set(c.chunk_id for c in paraphrase_chunks))
        assert overlap >= 1, f"Zero overlap for paraphrase: '{original}' vs '{paraphrase}'"
```

---

## Incremental Ingest (Monthly Updates)

```python
def incremental_ingest(s3_bucket: str, prefix: str) -> None:
    """Only process documents newer than last ingest timestamp."""
    last_ingest = get_last_ingest_timestamp_from_dynamo()
    s3 = boto3.client("s3")
    new_objects = [
        obj for obj in s3.list_objects_v2(Bucket=s3_bucket, Prefix=prefix)["Contents"]
        if obj["LastModified"] > last_ingest
    ]
    for obj in new_objects:
        process_document(obj["Key"])
    update_last_ingest_timestamp()
```

---

## Phase 4 Plan File Mapping

| Plan | Scope | Key Files |
|------|-------|-----------|
| 04-01 | PDF parsing + chunking + DynamoDB ingest pipeline for 20+ county docs | `knowledge/pipeline/ingest_pdf.py` |
| 04-02 | Hybrid retrieval (BM25 candidates → embedding re-rank) + per-candidate score logging | `backend/app/agents/retrieval.py` (upgrade) |
| 04-03 | Citation quality (page/section attribution) + paraphrase tests + Phase 4 eval | `evals/phase-4-eval.py` |
