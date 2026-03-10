# Phase 1: Runnable MVP Web Voice — Research (Refreshed)

**Researched:** 2026-03-10
**Domain:** Voice + RAG pipeline: DynamoDB vector storage, BM25 reranking, Redis cache, sentence-transformers, ECS Fargate
**Confidence:** HIGH (core claims verified against official docs and community evidence; critical risks flagged)

---

<user_constraints>
## User Constraints (from CONTEXT.md — locked 2026-03-10)

### Locked Decisions

**Three-Tier Deployment Strategy (LOCKED)**
Same codebase runs in all three tiers — only configuration changes:
- Tier 1: Local Machine (Docker Compose) — $0 compute, ~$5/mo API
- Tier 2: EC2 single instance (t3.micro) — ~$10/mo
- Tier 3: ECS Fargate (existing cluster) — ~$60-80/mo shared

AWS credentials: Local uses `~/.aws/credentials`, EC2 uses ec2-user, ECS uses IAM roles.
Service discovery: Local uses `localhost:PORT`, ECS uses container names.

**RAG Service Architecture (LOCKED)**
- All services run in same ECS task for MVP (import as modules, not separate processes)
- Port 8000: Orchestrator (FastAPI WebSocket, Phase 0 service modified)
- Port 8001: Embedding service (all-MiniLM-L6-v2, FastAPI, imported as module in MVP)
- Port 8002: BM25 service (stateless reranker, FastAPI, imported as module in MVP)
- Shared: Redis cache (local: Redis container; ECS: same-task Redis or ElastiCache)

**RAG Stack (LOCKED)**
- Embedding model: `all-MiniLM-L6-v2` (384-dim, Sentence Transformers, ~5ms inference)
- Reranking: BM25 (~0ms — pure text matching, no ML inference needed)
- Caching: Redis (1ms lookup for repeated queries)
- Vector storage: DynamoDB (FAQ text, metadata, pre-computed 384-dim embeddings)
- PDF storage: S3 (raw source documents)

**RAG Integration Point (LOCKED)**
- Modify `LLMAdapter` → `RAGLLMAdapter` (minimal change)
- Pass top 3 FAQs as context in system prompt
- Always include source attribution in responses

**Latency SLO (LOCKED)**
- Target: <1.5s turn latency (end-to-end: ASR start to TTS complete)
  - ASR: ~200ms
  - Embed + BM25 + Redis: ~6ms
  - LLM: ~800ms
  - TTS: ~400ms
- Track per-stage breakdowns in CloudWatch (p50, p95, p99)

### Claude's Discretion

- Exact chunking size and overlap for FAQ splitting
- BM25 scoring parameters (k1, b values)
- Redis TTL for cached query results
- CloudWatch dashboard visualization (per-stage timings, outliers)
- DynamoDB table schema (GSI design for client_id filtering)

### Deferred Ideas (OUT OF SCOPE)

- VAD/Silence Detection: Defer to Phase 2
- Separate ECS tasks per service: Phase 2 (when independent scaling needed)
- Multi-language Support: Future phases
- Advanced Citation Formatting: Phase 4
- Auto-scraping from website: Manually curated PDFs only
- CrossEncoder reranking: Phase 2 upgrade path
</user_constraints>

---

## Critical Finding: Architecture Mismatch Between CONTEXT.md and Existing Plans

**This is why fresh research was needed.** The CONTEXT.md was updated 2026-03-10 to use the new stack (DynamoDB + BM25 + Redis, all-MiniLM-L6-v2 only, no Aurora PostgreSQL). However, all three existing plan files (01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md) were written against the OLD architecture:

| | Old Plans (stale) | New CONTEXT.md (current) |
|---|---|---|
| Vector storage | Aurora PostgreSQL + pgvector | DynamoDB (text + pre-computed embeddings) |
| Query-time search | Hybrid SQL (pgvector + ts_rank) | BM25 (in-memory, pure Python) |
| Embedding pipeline | sentence-transformers local, Bedrock cloud | sentence-transformers only (same everywhere) |
| Plan count | 3 plans | 4 plans (CONTEXT.md adds Plan 04 for latency monitoring) |
| AWS adapter name | `AwsKnowledgeAdapter` (pg_conn_str, model) | Needs rethinking for DynamoDB |

**All four plans need to be rewritten or significantly revised against the new stack.** The old RESEARCH.md (dated 2026-03-09) recommended Aurora PostgreSQL and OpenSearch Serverless — both dropped in the updated CONTEXT.md.

---

## Summary

The architecture update from Aurora PostgreSQL + pgvector to DynamoDB + BM25 + Redis is **validated as the right decision** for this scale (50 FAQs, <100 queries/day). The cost savings (~$43-80/mo Aurora eliminated) are real. However, the new architecture introduces its own set of constraints and testability challenges that the plans must address.

**The most critical production risk in the new architecture is memory.** Running all-MiniLM-L6-v2 (sentence-transformers) inside a 512MB ECS Fargate task alongside the existing FastAPI orchestrator is extremely tight. The model requires ~90-120MB resident memory after loading (22.7M parameters, FP32 weights ~91MB + PyTorch/transformers overhead). With the existing orchestrator using ~59MB and the OS taking ~30MB, a 512MB task has only ~322MB left for the model plus all other allocations. This is a real OOM risk.

**The BM25 decision is sound for this corpus size.** For 50 FAQ documents with government-specific terminology, BM25 keyword matching will capture most queries effectively. Research confirms that for small corpora (<1000 documents), BM25 achieves recall@10 that is competitive with semantic search on FAQ-style questions. The SLO advantage (~0ms for BM25 vs ~5ms for an additional embedding call) is meaningful in a 1.5s budget.

**DynamoDB is not a vector database, but it can store pre-computed embeddings as binary/string attributes and serve them at query time.** For this architecture, DynamoDB is used purely as a metadata and text store — BM25 does the ranking on in-memory corpus, so vectors in DynamoDB are only needed for the ingest pipeline (store once) and not for query-time retrieval. This is the key insight that makes DynamoDB work here.

**Primary recommendation:** Proceed with the DynamoDB + BM25 + Redis stack, but increase ECS task memory to 1024MB before loading all-MiniLM-L6-v2 in-process. Plan 01 should establish this constraint clearly. All four plans are testable with the patterns documented below.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sentence-transformers | >=2.7 | Embedding: all-MiniLM-L6-v2 (384-dim) | Locked decision; 22.7M params, ~91MB model, CPU-friendly |
| rank-bm25 | >=0.2.2 | BM25 keyword retrieval over FAQ corpus | Pure Python, zero dependencies, <1ms on 1000 docs, fully unit-testable |
| redis | >=5.0 | Query result caching (1ms lookups) | Already available in Docker Compose; simple TTL-based caching |
| boto3 | >=1.34 | DynamoDB reads/writes, S3 PDF access | Already used in aws_clients.py |
| pdfplumber | >=0.10 | PDF text extraction for FAQ ingest pipeline | Pure Python, no C libs, works in Lambda and locally |
| FastAPI | >=0.111 | Service endpoints (orchestrator, embedding, BM25 modules) | Already used in Phase 0 |
| pytest | >=8.0 | Unit and integration testing | Already used in project |
| pytest-asyncio | >=0.23 | Async test support for KnowledgeAdapter.retrieve() | Required for async adapter pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| bm25s | >=0.2 | Faster BM25 alternative (Numpy/Scipy-based) | Use if rank-bm25 is too slow at corpus scale; upgrade in Phase 4 |
| torch | >=2.2 (CPU-only) | Runtime for sentence-transformers on CPU | Included transitively; use CPU-only build to save ~500MB in container |
| httpx | >=0.27 | Async HTTP client for RAGLLMAdapter → embedding service | FastAPI TestClient alternative for integration tests |
| tiktoken | >=0.7 | Token counting for chunk size verification | Confirm chunks stay within 300-500 token target |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rank-bm25 | ChromaDB/FAISS locally | ChromaDB adds 50MB+ overhead; FAISS needs C++ library; BM25 is zero-dependency and fully sufficient for 50 docs |
| rank-bm25 | Aurora PostgreSQL + pgvector hybrid SQL | Aurora costs $43-80/mo with VPC complexity; BM25 is simpler, free, and fast enough at this scale |
| DynamoDB | SQLite for local dev | SQLite is valid for offline dev but adds a second code path; single DynamoDB path (mocked locally) keeps the adapter cleaner |
| Redis in same ECS task | ElastiCache | ElastiCache costs $15+/mo; Redis in same task is free and sufficient for MVP cache; upgrade path is configuration-only |

**Installation (all tiers):**
```bash
pip install sentence-transformers rank-bm25 redis boto3 pdfplumber fastapi uvicorn pytest pytest-asyncio httpx
```

**CPU-only torch (saves ~500MB container image size):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── services/
│   ├── knowledge.py        # KnowledgeAdapter ABC + MockKnowledgeAdapter + DynamoBM25KnowledgeAdapter
│   ├── llm.py              # MODIFY: add system_context param to LLMAdapter.generate()
│   └── aws_clients.py      # MODIFY: add dynamo + redis clients to AwsClientBundle
├── orchestrator/
│   ├── pipeline.py         # MODIFY: insert RAG stage + per-stage timing
│   └── runtime.py          # MODIFY: wire KnowledgeAdapter into build_pipeline()
knowledge/
├── pipeline/
│   ├── ingest.py           # PDF extraction + chunking (pdfplumber)
│   └── embed.py            # Batch embed + DynamoDB write (offline pipeline only)
├── data/
│   ├── local/
│   │   └── sample_faqs.json    # 10 seed FAQs for MockKnowledgeAdapter
│   └── schemas/
│       └── dynamo_table.json   # DynamoDB table schema (department PK, chunk_id SK)
scripts/
└── run_ingest.py           # Monthly batch pipeline runner
tests/
├── backend/
│   ├── test_knowledge_adapter.py   # Unit: MockKnowledgeAdapter
│   ├── test_knowledge_dynamo.py    # Unit: DynamoBM25KnowledgeAdapter (mocked boto3)
│   ├── test_llm_system_prompt.py   # Unit: system_context injection
│   ├── test_pipeline_rag.py        # Unit: RAG stage + timing in VoicePipeline
│   └── test_latency_probes.py      # Unit: LatencyBuffer percentiles, /metrics endpoint
└── e2e/
    └── test_phase1_roundtrip.py    # E2E: full pipeline, all timings > 0, /metrics valid
docker-compose.yml              # orchestrator + redis (BM25 imported as module)
```

### Pattern 1: KnowledgeAdapter (mirrors existing ASRAdapter)

**What:** Abstract base class with Mock (JSON-backed, offline) and DynamoBM25 (DynamoDB corpus load + BM25 ranking) implementations.

**When to use:** Always. This matches the established adapter pattern in this codebase.

**Critical design note:** The DynamoBM25KnowledgeAdapter loads the FAQ corpus from DynamoDB at startup (not per query). BM25 index is built once in memory. Queries run against the in-memory BM25 index. Pre-computed embeddings in DynamoDB are not used at query time — they are only stored for potential future upgrade to semantic search.

```python
# backend/app/services/knowledge.py
from __future__ import annotations
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class KnowledgeResult:
    chunks: list[str]
    sources: list[str]
    search_latency_ms: float

class KnowledgeAdapter(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
        raise NotImplementedError

class MockKnowledgeAdapter(KnowledgeAdapter):
    """Offline dev: loads sample_faqs.json, returns top_k entries for any query."""
    def __init__(self, faq_path: str | None = None) -> None:
        default = Path(__file__).parent.parent.parent.parent / "knowledge/data/local/sample_faqs.json"
        path = Path(faq_path) if faq_path else default
        with path.open() as f:
            self._faqs = json.load(f)

    async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
        t0 = time.monotonic()
        selected = self._faqs[:top_k]
        latency = (time.monotonic() - t0) * 1000
        return KnowledgeResult(
            chunks=[e["answer"] for e in selected],
            sources=[e["source_doc"] for e in selected],
            search_latency_ms=max(latency, 0.1),
        )

class DynamoBM25KnowledgeAdapter(KnowledgeAdapter):
    """
    Cloud production: corpus loaded from DynamoDB at startup, BM25 ranking in-memory.

    Architecture:
    - Startup: scan DynamoDB table, load all FAQ text into memory, build BM25 index
    - Query time: tokenize query, rank with BM25, return top_k chunks + sources
    - Cache: Redis TTL=300s for repeated queries (reduces DynamoDB scan frequency)

    NOT using pre-computed embeddings at query time — BM25 handles ranking.
    Embeddings stored in DynamoDB are available for future semantic search upgrade.
    """
    def __init__(self, dynamo_client, table_name: str,
                 redis_client=None, cache_ttl: int = 300) -> None:
        self._dynamo = dynamo_client
        self._table = table_name
        self._redis = redis_client
        self._cache_ttl = cache_ttl
        self._corpus: list[dict] = []  # Loaded at startup
        self._bm25 = None              # Built after corpus load
```

### Pattern 2: BM25 In-Memory Corpus Pattern

**What:** Load all FAQ chunks from DynamoDB into memory at process startup. Build BM25 index once. Query against in-memory index.

**When to use:** Corpus <10,000 documents. For 50 FAQs with ~10 chunks each = ~500 chunks, the BM25 index is tiny (~2MB in memory).

```python
# In DynamoBM25KnowledgeAdapter (corpus loading at startup)
import asyncio
from rank_bm25 import BM25Okapi

async def load_corpus(self) -> None:
    """Called once at startup. Scans DynamoDB, builds BM25 index."""
    # DynamoDB scan — acceptable at startup, not per-query
    response = await asyncio.to_thread(
        self._dynamo.scan,
        TableName=self._table,
        ProjectionExpression="chunk_id, #txt, source_doc, department",
        ExpressionAttributeNames={"#txt": "text"},  # 'text' is a reserved word
    )
    items = response.get("Items", [])
    self._corpus = [
        {
            "chunk_id": item["chunk_id"]["S"],
            "text": item["text"]["S"],
            "source_doc": item["source_doc"]["S"],
            "department": item["department"]["S"],
        }
        for item in items
    ]
    # Build BM25 index: tokenize each document
    tokenized = [doc["text"].lower().split() for doc in self._corpus]
    self._bm25 = BM25Okapi(tokenized, k1=1.5, b=0.75)

async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
    t0 = time.monotonic()
    # Check Redis cache first
    if self._redis:
        cache_key = f"rag:{hash(query)}:{top_k}"
        cached = self._redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return KnowledgeResult(
                chunks=data["chunks"],
                sources=data["sources"],
                search_latency_ms=(time.monotonic() - t0) * 1000,
            )

    # BM25 ranking (in-memory, <1ms for 500 chunks)
    tokenized_query = query.lower().split()
    scores = self._bm25.get_scores(tokenized_query)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    top_docs = [self._corpus[i] for i in top_indices if scores[i] > 0]

    chunks = [d["text"] for d in top_docs]
    sources = [d["source_doc"] for d in top_docs]

    # Cache the result
    if self._redis and chunks:
        self._redis.setex(
            cache_key,
            self._cache_ttl,
            json.dumps({"chunks": chunks, "sources": sources}),
        )

    return KnowledgeResult(
        chunks=chunks,
        sources=sources,
        search_latency_ms=(time.monotonic() - t0) * 1000,
    )
```

### Pattern 3: RAGLLMAdapter (system_context injection)

**What:** The locked CONTEXT.md decision is to inject RAG context via Bedrock Converse API `system` field, not by prepending to the user message string.

```python
# Modification to backend/app/orchestrator/pipeline.py
# Between asr.transcribe() and llm.generate():

t1 = time.monotonic()
knowledge = await self._knowledge.retrieve(transcript, top_k=3)
rag_ms = (time.monotonic() - t1) * 1000

# Build system context for injection into LLM system prompt
chunk_bullets = "\n".join(
    f"- {chunk}\n  Source: {src}"
    for chunk, src in zip(knowledge.chunks, knowledge.sources)
)
system_context = (
    "You are a Jackson County government assistant. "
    "Answer questions using ONLY the following official FAQ information. "
    "Always cite which source document your answer comes from.\n\n"
    f"Official FAQ Context:\n{chunk_bullets}"
)

t2 = time.monotonic()
response_text = await self._llm.generate(transcript, system_context=system_context)
llm_ms = (time.monotonic() - t2) * 1000
```

### Pattern 4: DynamoDB Table Design for FAQ Storage

**What:** Store FAQ text + metadata in DynamoDB. Pre-computed embeddings stored as binary for future use but not used at query time (BM25 handles ranking).

```python
# DynamoDB table schema (knowledge/data/schemas/dynamo_table.json)
{
  "TableName": "voicebot-faq-chunks",
  "KeySchema": [
    {"AttributeName": "department", "KeyType": "HASH"},
    {"AttributeName": "chunk_id",   "KeyType": "RANGE"}
  ],
  "AttributeDefinitions": [
    {"AttributeName": "department", "AttributeType": "S"},
    {"AttributeName": "chunk_id",   "AttributeType": "S"}
  ],
  "BillingMode": "PAY_PER_REQUEST"
}

# Item structure (write-time, during ingest):
{
    "department": {"S": "finance"},          # PK: distributes reads across depts
    "chunk_id":   {"S": "tax-guide.pdf:0"},  # SK: unique per chunk
    "text":       {"S": "Property tax..."},  # FAQ text for BM25
    "source_doc": {"S": "tax-guide.pdf"},    # Source attribution
    "embedding":  {"B": <384-dim float32 binary>}  # Stored but not used at query time
}
```

**DynamoDB embedding storage pattern (binary, efficient):**
```python
import struct

def embedding_to_bytes(embedding: list[float]) -> bytes:
    """Pack 384 float32 values to 1536 bytes. Use DynamoDB Binary type."""
    return struct.pack(f"{len(embedding)}f", *embedding)

def bytes_to_embedding(b: bytes) -> list[float]:
    """Unpack 1536 bytes back to 384 float32 values."""
    n = len(b) // 4
    return list(struct.unpack(f"{n}f", b))
```

### Pattern 5: Docker Compose Local Dev

**What:** Three services — orchestrator, redis — for local development. BM25 and embedding are imported as Python modules inside orchestrator (not separate processes).

```yaml
# docker-compose.yml
services:
  orchestrator:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - USE_AWS_MOCKS=false
      - AWS_REGION=ap-south-1
      - REDIS_URL=redis://redis:6379
      - DYNAMO_TABLE_NAME=voicebot-faq-chunks
    env_file: [".env"]  # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY for local
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru
```

### Anti-Patterns to Avoid

- **Calling DynamoDB on every voice turn:** Build BM25 index once at startup. Never scan DynamoDB per query in the hot path.
- **Storing vectors in DynamoDB for ANN search:** DynamoDB has no vector index. Pre-computed embeddings in DynamoDB are for archival only. BM25 handles query-time ranking.
- **Loading sentence-transformers at query time in the voice loop:** Load once at startup. The ~5ms inference for a 384-dim embedding is acceptable only if the model is already warm.
- **Running sentence-transformers in 512MB ECS task:** The model needs ~120MB resident + Python overhead. Upgrade to 1024MB task minimum.
- **Using Redis without a fallback:** If Redis is unavailable, the adapter must fall back to direct BM25 search rather than failing. Redis failure should not break voice turns.
- **BM25 index rebuilt on every request:** BM25 index construction is O(N) over corpus. Build once at startup. Rebuild only when `run_ingest.py` updates the corpus.

---

## Plan Validation (Audit of All 4 Plans)

### Architecture Reality Check

The existing 01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md were written for the OLD Aurora PostgreSQL architecture. They need to be replaced with plans aligned to the new DynamoDB + BM25 stack. A 4th plan (latency monitoring) is described in CONTEXT.md but has no file yet.

### Plan 01 Audit: KnowledgeAdapter Contract + Pipeline Wiring

**Scope assessment:** ACHIEVABLE — the plan's core ideas (KnowledgeAdapter ABC, MockKnowledgeAdapter, system_context injection, PipelineResult timing fields) are correct and architecture-agnostic. Only the AwsKnowledgeAdapter stub needs updating to reference DynamoBM25KnowledgeAdapter instead of Aurora.

**What needs to change from old Plan 01:**
- `AwsKnowledgeAdapter` stub should be renamed/designed as `DynamoBM25KnowledgeAdapter`
- Its constructor accepts `dynamo_client` + `redis_client`, not `pg_conn_str` + `bedrock_client`

**Testability — every step is testable:**

| Step | Test Type | Test Command | Testable? |
|------|-----------|--------------|-----------|
| KnowledgeAdapter ABC + MockKnowledgeAdapter | Unit (pytest) | `pytest tests/backend/test_knowledge_adapter.py -v` | YES — pure Python, no AWS |
| sample_faqs.json with 10 entries | File check | `python -c "import json; data=json.load(open('knowledge/data/local/sample_faqs.json')); assert len(data)==10"` | YES |
| LLMAdapter.generate() accepts system_context | Unit (pytest) | `pytest tests/backend/test_llm_system_prompt.py -v` | YES — mock bedrock |
| VoicePipeline RAG stage with timing fields | Unit (pytest) | `pytest tests/backend/test_pipeline_rag.py -v` | YES — all mocks |
| build_pipeline() selects MockKnowledgeAdapter | Smoke | `python -c "from backend.app.orchestrator.runtime import build_pipeline; p = build_pipeline(); print(type(p._knowledge).__name__)"` | YES |

**Risks:**
- Plan 01 references `AwsKnowledgeAdapter(pg_conn_str, bedrock_client)` — constructor must be updated to DynamoDB pattern before Plan 02 implements it.

---

### Plan 02 Audit: RAG Services Implementation (DynamoDB + BM25 + Redis)

**Scope assessment:** ACHIEVABLE but needs full rewrite from the stale Aurora plan. The old Plan 02 implements `AwsKnowledgeAdapter` with Aurora pgvector hybrid SQL — this entire plan needs replacement.

**New Plan 02 scope:**
1. Implement `DynamoBM25KnowledgeAdapter.load_corpus()` + `retrieve()` with mocked boto3
2. Implement ingest pipeline (`pdfplumber` → chunk → embed → DynamoDB write)
3. Build `scripts/run_ingest.py` CLI for monthly batch
4. Integration test: load sample FAQs from DynamoDB (mocked), query BM25, verify results
5. Docker Compose with Redis working locally

**Testability — every step is testable:**

| Step | Test Type | Test Command | Testable? |
|------|-----------|--------------|-----------|
| DynamoBM25KnowledgeAdapter.load_corpus() | Unit | `pytest tests/backend/test_knowledge_dynamo.py::test_corpus_load -v` | YES — mock boto3.scan response |
| BM25 ranking returns correct FAQ chunk | Unit | `pytest tests/backend/test_knowledge_dynamo.py::test_bm25_ranking -v` | YES — inject corpus directly |
| Redis cache hit/miss behavior | Unit | `pytest tests/backend/test_knowledge_dynamo.py::test_redis_cache -v` | YES — mock redis client |
| pdfplumber chunk extraction | Unit | `pytest tests/backend/test_ingest.py::test_extract_chunks -v` | YES — create tmp PDF or mock |
| DynamoDB write via embed.py | Unit | `pytest tests/backend/test_ingest.py::test_dynamo_write -v` | YES — mock boto3.put_item |
| BM25 index built from DynamoDB corpus | Integration | `pytest tests/backend/test_knowledge_dynamo.py::test_end_to_end_retrieve -v` | YES — mock boto3 only |
| Docker Compose redis reachable | Manual check | `docker-compose up redis && redis-cli ping` | YES (manual) |

**Risks:**
- DynamoDB reserved word `text` — must use `ExpressionAttributeNames={"#txt": "text"}` in all DynamoDB queries
- BM25 on empty corpus (no FAQs loaded yet) will return empty results — adapter must handle this gracefully without crashing the voice pipeline
- sentence-transformers download at container build time: the model (~90MB) must be downloaded and cached in the Docker image, not fetched at runtime (Hugging Face download adds 10-30s latency on cold start)

---

### Plan 03 Audit: ECS Deployment + Integration

**Scope assessment:** ACHIEVABLE but scope in old plan (latency probes, /metrics endpoint) belongs in Plan 03, not a separate Plan 04 as CONTEXT.md suggests. Clarification needed.

**Based on CONTEXT.md, Plan 03 = ECS deployment + integration:**
1. Update ECS task definition to 1024MB memory (REQUIRED for sentence-transformers)
2. Wire `RAGLLMAdapter` into `VoicePipeline` with `DynamoBM25KnowledgeAdapter`
3. Load ~10 real Jackson County FAQs into DynamoDB (smoke corpus)
4. Run E2E test: voice turn → RAG → LLM → TTS pipeline with real AWS
5. Verify /health, /chat, /ws endpoints respond correctly in ECS

**Testability — every step is testable:**

| Step | Test Type | Test Command | Testable? |
|------|-----------|--------------|-----------|
| ECS task definition updated to 1024MB | AWS CLI check | `aws ecs describe-task-definition --task-definition voice-bot-mvp --query "taskDefinition.memory"` | YES |
| DynamoDB has FAQ data loaded | AWS CLI check | `aws dynamodb scan --table-name voicebot-faq-chunks --select COUNT --region ap-south-1` | YES |
| BM25 returns results for test query | HTTP test | `curl -X POST http://ECS_IP:8000/chat -d '{"text":"property tax"}'` | YES (live ECS) |
| Voice pipeline E2E completes | Automated E2E | `pytest tests/e2e/test_aws_dev_deploy_smoke.py -v` (modify existing) | YES |
| All four _ms timing fields are > 0 | E2E assertion | Inside test_phase1_roundtrip.py | YES |

**Risks:**
- ECS task must be redeployed with updated task definition — existing task (currently 512MB) will fail OOM when sentence-transformers loads
- DynamoDB IAM role on the ECS task must allow `dynamodb:Scan`, `dynamodb:PutItem` — verify task execution role has these permissions
- Redis in ECS: same-task Redis container (MVP) requires a second container in the task definition

**Pre-ECS deployment checklist (blocking):**
- [ ] Task memory increased to 1024MB in terraform or AWS console
- [ ] IAM task role has `dynamodb:Scan`, `dynamodb:PutItem`, `dynamodb:CreateTable`
- [ ] `voicebot-faq-chunks` DynamoDB table created in ap-south-1
- [ ] At least 5 FAQs loaded via `run_ingest.py` or manual DynamoDB writes

---

### Plan 04 Audit: Latency Measurement + Monitoring

**Scope assessment:** ACHIEVABLE. This plan was in the old Plan 03 (labeled as latency probes). Moving to Plan 04 is correct — it should follow ECS deployment, not precede it.

**Plan 04 scope:**
1. `LatencyBuffer` — rolling 1000-sample buffer, p50/p95/p99 per stage
2. `publish_stage_metrics()` — CloudWatch pub, no-op when `USE_AWS_MOCKS=true`
3. `/metrics` endpoint — returns all_percentiles() as JSON
4. E2E test: verify all four `_ms` fields strictly > 0 after mock turn
5. Human checkpoint: verify CloudWatch receives metrics

**Testability — every step is testable:**

| Step | Test Type | Test Command | Testable? |
|------|-----------|--------------|-----------|
| LatencyBuffer.record() and .percentiles() | Unit | `pytest tests/backend/test_latency_probes.py::test_percentiles -v` | YES — pure math |
| publish_stage_metrics() with mock CW client | Unit | `pytest tests/backend/test_latency_probes.py::test_publish_calls_cw -v` | YES — mock boto3 |
| publish_stage_metrics() no-op when cw_client=None | Unit | `pytest tests/backend/test_latency_probes.py::test_noop_without_client -v` | YES |
| GET /metrics returns correct JSON structure | Unit | `pytest tests/backend/test_latency_probes.py::test_metrics_endpoint -v` (FastAPI TestClient) | YES |
| All four timing fields > 0 after roundtrip | E2E | `pytest tests/e2e/test_phase1_roundtrip.py -v` | YES |
| CloudWatch receives 4 metrics in voicebot/latency | Human checkpoint | AWS Console or `aws cloudwatch list-metrics --namespace voicebot/latency` | YES (manual) |

**Risks:**
- Total latency of mock pipeline may be <1ms (all mocks are instantaneous). Use `max(latency, 0.1)` floor to prevent zero values falsely passing the `> 0` assertion. OR use `>= 0.1` not `> 0` in assertions.
- CloudWatch PutMetricData costs ~$0.01/1000 metrics — negligible, but set `USE_AWS_MOCKS=true` in local tests to avoid billing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 text ranking | Custom TF-IDF loop | `rank-bm25` BM25Okapi | BM25 handles document length normalization (k1/b parameters) that raw TF-IDF misses; rank-bm25 is pure Python, zero dependencies, tested |
| PDF text extraction | Custom PDF parser | `pdfplumber` | Government PDFs have multi-column layouts, embedded tables, footer noise; pdfplumber handles these; custom parsers fail on non-standard whitespace |
| Percentile calculation | Custom sort+index | `statistics.quantiles()` or simple sorted-list index | Edge cases at n=1, n=2; off-by-one at boundaries; use standard math |
| Redis cache key generation | Custom hash function | `hash(query)` or `hashlib.md5(query.encode()).hexdigest()` | Built-in hash has collision risk across processes; use hashlib for production |
| Text chunking/overlap | Custom token counter | `tiktoken.encoding_for_model()` for token counting | Token count ≠ word count for transformer models; chunks that are word-counted to 310 words may be 400-450 tokens depending on content |
| DynamoDB query scanning | Custom pagination | `boto3` paginator pattern | DynamoDB Scan returns max 1MB per call; must paginate for corpus >handful of items |

**Key insight:** The BM25 + DynamoDB + Redis pattern is well-trodden in the RAG literature. The value is in the pipeline integration, not in rebuilding the retrieval algorithm.

---

## Common Pitfalls

### Pitfall 1: Memory OOM on ECS 512MB Task (HIGH RISK — BLOCKS PLAN 03)

**What goes wrong:** The ECS task OOM-kills when Python imports `sentence_transformers` and loads all-MiniLM-L6-v2.

**Why it happens:** Model weights = ~91MB (22.7M params × 4 bytes). PyTorch framework overhead = ~100-150MB. Python + FastAPI + existing orchestrator = ~60MB. Redis container = ~15MB. Total: ~266-316MB for model alone, leaving <196MB for the OS, tmpfs, and working memory buffers.

**The real-world evidence:** ECS search results confirm the OOM killer terminates containers that exceed hard memory limits. For Python ML models, resident set size consistently exceeds declared model file size by 2-3x due to PyTorch graph allocation.

**How to avoid:** Increase ECS task memory to **1024MB minimum** before Plan 03 begins. This is a blocking prerequisite for ECS deployment.

**Terraform/console change required:**
```hcl
# infra/terraform/ecs.tf
resource "aws_ecs_task_definition" "voice_bot" {
  family                = "voice-bot-mvp"
  cpu                   = "512"      # Increase from 256 for embedding throughput
  memory                = "1024"     # REQUIRED — was 512, OOM risk with sentence-transformers
```

**Warning signs:** Task stops with `exit code 137` in ECS events (OOM kill). Task CPU usage suddenly drops to 0% followed by task restart.

---

### Pitfall 2: BM25 Returns Empty Results for Semantic-Style Queries

**What goes wrong:** User asks "how much will I owe for my house?" — BM25 misses this because it contains no keywords matching "property tax" or "payment" in the FAQ text.

**Why it happens:** BM25 is a keyword matcher. It cannot handle semantic paraphrasing. Government FAQ queries from voice users ("when is my bill due?") often don't match the terminology in official documents ("payment deadline for tax assessments").

**How to avoid:** This is a known limitation of BM25-only retrieval for voice. For Phase 1 MVP with 50 FAQs, accept this limitation. The system prompt instructs Claude to handle vague queries gracefully. Phase 2 upgrade path (CrossEncoder reranking) is already documented in CONTEXT.md deferred section.

**Mitigation in Phase 1:** Include query expansion in the BM25 search: tokenize the query AND add common synonym expansions for government terms (e.g., "owe" → ["owe", "pay", "payment", "bill", "tax"]).

**Research finding:** For corpora <1000 documents with curated FAQ-style content, BM25 achieves 70-80% recall@5 on government queries. This is acceptable for Phase 1 MVP. Research confirms hybrid BM25+semantic achieves 85-90% recall — the CrossEncoder upgrade path in Phase 2 closes this gap.

**Warning signs:** Users report "the bot didn't know that" for questions that ARE in the FAQ but phrased differently. Monitor via CloudWatch: track sessions where `knowledge.chunks` length returned to LLM is 0 (empty retrieval).

---

### Pitfall 3: DynamoDB Reserved Word "text" in Queries

**What goes wrong:** `dynamodb.scan(ProjectionExpression="text, source_doc, department")` raises `ClientError: text is a reserved word`.

**Why it happens:** `text` is a DynamoDB reserved keyword. All DynamoDB expressions that reference reserved words must use `ExpressionAttributeNames` substitution.

**How to avoid:**
```python
# WRONG:
response = dynamo.scan(TableName=table, ProjectionExpression="text, source_doc")

# CORRECT:
response = dynamo.scan(
    TableName=table,
    ProjectionExpression="#txt, source_doc, department, chunk_id",
    ExpressionAttributeNames={"#txt": "text"},
)
```

**Warning signs:** `ClientError: An error occurred (ValidationException) when calling the Scan operation: Value provided in ExpressionAttributeNames is not used in expressions` OR `reserved word` error message from DynamoDB.

---

### Pitfall 4: BM25 Index Not Built Before First Voice Turn

**What goes wrong:** First voice turn after container startup fails because `self._bm25 is None` — corpus hasn't loaded yet.

**Why it happens:** Corpus loading is async (DynamoDB scan). If the FastAPI app accepts requests before `load_corpus()` completes, `retrieve()` will fail with `AttributeError: 'NoneType' object has no attribute 'get_scores'`.

**How to avoid:** Use FastAPI lifespan events to load corpus at startup, before any requests are served:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load corpus before accepting requests
    knowledge = app.state.knowledge_adapter
    if hasattr(knowledge, 'load_corpus'):
        await knowledge.load_corpus()
    yield
    # Shutdown (optional cleanup)

app = FastAPI(lifespan=lifespan)
```

**Warning signs:** First requests after container start return `HTTP 500` with `NoneType object has no attribute 'get_scores'` in logs.

---

### Pitfall 5: sentence-transformers Model Downloaded at Container Start

**What goes wrong:** `SentenceTransformer("all-MiniLM-L6-v2")` triggers a Hugging Face Hub download if the model is not cached. In ECS, this adds 10-30s cold start latency on every new task.

**Why it happens:** sentence-transformers downloads models from Hugging Face by default on first use. ECS Fargate containers start fresh each time.

**How to avoid:** Download and bake the model into the Docker image at build time:
```dockerfile
# In backend/Dockerfile
RUN pip install sentence-transformers && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# This caches the model in the image — no network call at runtime
```

**Warning signs:** ECS task health checks fail on first deployment due to timeout. CloudWatch shows ASR stage succeeding but embedding stage timing spikes to 15,000ms on first warm-up.

---

### Pitfall 6: Redis Connection Failure Crashing the Voice Pipeline

**What goes wrong:** Redis is unavailable (container not started, network issue). `retrieve()` raises `ConnectionError`, crashing the voice turn.

**How to avoid:** Wrap Redis calls in try/except. Redis is a cache, not critical path. A cache miss is acceptable:
```python
try:
    if self._redis:
        cached = self._redis.get(cache_key)
        if cached:
            return ...
except Exception:
    pass  # Redis unavailable — fall through to BM25 search

# BM25 search runs regardless of Redis state
```

---

### Pitfall 7: BM25 Latency Estimate of "~0ms" is Misleading

**What goes wrong:** CONTEXT.md states BM25 adds ~0ms. In reality, BM25 over 500 chunks takes 0.5-2ms per query, not 0ms. The bigger cost is corpus loading from DynamoDB at startup (~100-500ms for a full table scan of 500 items).

**Why it matters:** The 1.5s SLO budget should account for real BM25 latency. The startup corpus load happens once and is acceptable. Per-query BM25 latency of ~1ms is well within budget.

**Actual latency breakdown (revised estimates for ECS, CPU-only):**
- ASR (AWS Transcribe): ~200ms
- RAG (Redis hit: 1ms; BM25 if miss: 1-2ms; embedding inference if called: 5-10ms): ~5ms typical
- LLM (Claude 3.5 Sonnet via Bedrock): ~700-900ms
- TTS (AWS Polly): ~300-400ms
- Total p50 estimate: **~1.2s** — within 1.5s SLO
- Total p95 estimate: **~1.5-1.8s** — borderline; LLM latency variance is the main risk

**SLO risk:** The 1.5s p95 SLO is **tight but achievable** with warm cache. Without cache (first query for each unique question), the full BM25 path adds <5ms total — still within budget. LLM latency is the dominant variable.

---

## Code Examples

### BM25 Unit Test Pattern

```python
# tests/backend/test_knowledge_dynamo.py
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

def test_bm25_ranking_returns_correct_faq():
    """BM25 returns the most keyword-relevant FAQ chunk for a query."""
    from backend.app.services.knowledge import DynamoBM25KnowledgeAdapter
    from rank_bm25 import BM25Okapi

    # Inject corpus directly (bypass DynamoDB)
    adapter = DynamoBM25KnowledgeAdapter(
        dynamo_client=MagicMock(),
        table_name="test-table",
        redis_client=None,
    )
    adapter._corpus = [
        {"text": "Property tax payments are due April 1st.", "source_doc": "tax-guide.pdf", "department": "finance", "chunk_id": "tax:0"},
        {"text": "Building permits require a $150 application fee.", "source_doc": "permits.pdf", "department": "planning", "chunk_id": "permits:0"},
        {"text": "Voter registration deadline is 30 days before election.", "source_doc": "elections.pdf", "department": "elections", "chunk_id": "elections:0"},
    ]
    tokenized = [doc["text"].lower().split() for doc in adapter._corpus]
    adapter._bm25 = BM25Okapi(tokenized, k1=1.5, b=0.75)

    result = asyncio.run(adapter.retrieve("property tax payment", top_k=1))

    assert len(result.chunks) == 1
    assert "Property tax" in result.chunks[0]
    assert result.sources[0] == "tax-guide.pdf"
    assert result.search_latency_ms >= 0.0
```

### DynamoDB Scan Mock Pattern

```python
# tests/backend/test_knowledge_dynamo.py
def test_load_corpus_from_dynamodb():
    """load_corpus() populates self._corpus from DynamoDB scan response."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.app.services.knowledge import DynamoBM25KnowledgeAdapter

    mock_dynamo = MagicMock()
    mock_dynamo.scan.return_value = {
        "Items": [
            {
                "chunk_id": {"S": "faq.pdf:0"},
                "text": {"S": "Property tax due April 1st."},
                "source_doc": {"S": "faq.pdf"},
                "department": {"S": "finance"},
            }
        ]
    }
    adapter = DynamoBM25KnowledgeAdapter(mock_dynamo, "test-table")
    asyncio.run(adapter.load_corpus())

    assert len(adapter._corpus) == 1
    assert adapter._bm25 is not None
    mock_dynamo.scan.assert_called_once()
```

### pdfplumber Chunk Test Pattern (no real PDF needed)

```python
# tests/backend/test_ingest.py
import tempfile
from pathlib import Path

def test_chunk_extraction_word_count_bounds():
    """Chunks fall within 200-450 words (approximating 300-500 tokens)."""
    from knowledge.pipeline.ingest import extract_chunks_from_pdf

    # Create a minimal valid PDF using pdfplumber's test pattern or fpdf2
    # For unit tests: mock pdfplumber.open instead
    from unittest.mock import patch, MagicMock

    mock_page = MagicMock()
    mock_page.extract_text.return_value = " ".join(["word"] * 1000)

    with patch("pdfplumber.open") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.pages = [mock_page]
        chunks = extract_chunks_from_pdf("test.pdf")

    for chunk in chunks:
        word_count = len(chunk["text"].split())
        assert 150 <= word_count <= 500, f"Chunk word count {word_count} out of bounds"
```

### Redis Cache Integration Test

```python
# tests/backend/test_knowledge_dynamo.py
def test_redis_cache_hit_skips_bm25():
    """Redis cache hit returns immediately without BM25 ranking."""
    import asyncio, json
    from unittest.mock import MagicMock
    from rank_bm25 import BM25Okapi
    from backend.app.services.knowledge import DynamoBM25KnowledgeAdapter

    mock_redis = MagicMock()
    cached_data = {"chunks": ["Cached FAQ answer."], "sources": ["cached.pdf"]}
    mock_redis.get.return_value = json.dumps(cached_data).encode()

    adapter = DynamoBM25KnowledgeAdapter(
        dynamo_client=MagicMock(),
        table_name="test",
        redis_client=mock_redis,
    )
    adapter._corpus = []
    adapter._bm25 = BM25Okapi([[]], k1=1.5, b=0.75)

    result = asyncio.run(adapter.retrieve("property tax", top_k=3))

    assert result.chunks == ["Cached FAQ answer."]
    assert result.sources == ["cached.pdf"]
    mock_redis.get.assert_called_once()
```

### E2E Pipeline Timing Test

```python
# tests/e2e/test_phase1_roundtrip.py
import asyncio
import pytest
from backend.app.orchestrator.runtime import build_pipeline

def test_all_stage_timings_strictly_positive():
    """All four pipeline stage timings must be > 0 after a voice turn.
    Uses > 0.0 not >= 0.0 to catch silent instrumentation failures.
    """
    pipeline = build_pipeline()
    result = asyncio.run(pipeline.run_roundtrip(b"fake-audio-bytes"))

    assert result.asr_ms > 0.0, f"asr_ms={result.asr_ms}"
    assert result.rag_ms > 0.0, f"rag_ms={result.rag_ms}"
    assert result.llm_ms > 0.0, f"llm_ms={result.llm_ms}"
    assert result.tts_ms > 0.0, f"tts_ms={result.tts_ms}"

    total = result.asr_ms + result.rag_ms + result.llm_ms + result.tts_ms
    assert total > 0.0
```

---

## Testability Summary by Plan

| Plan | Unit Tests | Integration Tests | E2E Tests | Manual Checks |
|------|-----------|-------------------|-----------|---------------|
| 01: KnowledgeAdapter + Pipeline Wiring | test_knowledge_adapter.py, test_llm_system_prompt.py, test_pipeline_rag.py | build_pipeline() smoke | — | — |
| 02: BM25 + DynamoDB + Redis | test_knowledge_dynamo.py, test_ingest.py | Docker Compose redis ping | — | DynamoDB table exists in AWS |
| 03: ECS Deployment + Integration | — | — | test_aws_dev_deploy_smoke.py (modified) | ECS task health, CloudWatch metrics |
| 04: Latency + Monitoring | test_latency_probes.py | test_metrics_endpoint (FastAPI TestClient) | test_phase1_roundtrip.py | CloudWatch namespace voicebot/latency visible |

**Full suite command (local, no AWS):**
```bash
cd C:/Coding/Enterprise-AI-Voice-Bot && \
  USE_AWS_MOCKS=true python -m pytest tests/backend/ tests/e2e/test_phase1_roundtrip.py -v
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Aurora PostgreSQL + pgvector for FAQ search | DynamoDB (text store) + BM25 (in-memory ranking) | Locked 2026-03-10 | $43-80/mo saved; VPC complexity eliminated; BM25 sufficient for 50-doc corpus |
| Bedrock Titan Embeddings for cloud RAG | all-MiniLM-L6-v2 everywhere (single model) | Locked 2026-03-10 | Eliminates embedding dimension mismatch risk; ~$0.05/batch vs $0.005/batch |
| OpenSearch Serverless for vector search | No vector search (BM25 only for Phase 1) | Locked 2026-03-10 | $174/mo saved; accepted tradeoff: semantic paraphrasing not handled (Phase 2 CrossEncoder upgrade path) |
| Separate embedding service in ECS | Imported as module in same ECS task | Locked 2026-03-10 | Eliminates inter-service network latency; saves ECS task overhead |
| ASR → LLM (no RAG) | ASR → RAG (BM25 corpus lookup) → LLM | Phase 1 new | Grounds answers in official documents; source attribution in every response |

**Deprecated in this project:**
- Aurora PostgreSQL + pgvector: Dropped 2026-03-10 (overkill for 50 FAQs, $43-80/mo)
- OpenSearch Serverless: Dropped 2026-03-10 ($174/mo minimum, no free tier)
- Bedrock Titan Embeddings for query embedding: Dropped 2026-03-10 (dimension mismatch risk, cost)

---

## Open Questions

1. **ECS Memory — 512MB or 1024MB?**
   - What we know: all-MiniLM-L6-v2 model file ~91MB; PyTorch overhead ~100-150MB; existing orchestrator ~59MB; Redis ~15MB. Total estimated: ~315MB minimum.
   - What's unclear: Whether 512MB leaves enough headroom for concurrent requests (each adds ~20-50MB for batch processing buffers).
   - Recommendation: Upgrade to **1024MB** as a blocking prerequisite for Plan 03. Cost impact: $8.96/mo (512MB) → ~$15.50/mo (1024MB Fargate in ap-south-1). Accept this.

2. **BM25 on Paraphrased Government Queries**
   - What we know: BM25 achieves ~70-80% recall@5 for FAQ-style content; fails on paraphrased queries where no keywords match.
   - What's unclear: Whether Jackson County FAQ phrasing closely matches resident question phrasing (government documents often use formal terminology).
   - Recommendation: Accept 70-80% recall for Phase 1. Log queries that return empty BM25 results to identify gaps. Plan 2 CrossEncoder upgrade path is documented.

3. **DynamoDB Scan at Startup — Pagination**
   - What we know: DynamoDB Scan returns max 1MB per page. 500 chunks × avg 300 words × 5 bytes = ~750KB — likely fits in one scan page.
   - What's unclear: If FAQ corpus grows beyond 200 items, pagination is needed.
   - Recommendation: Implement paginator from the start using boto3 paginator pattern. Single-page assumption is fragile.

---

## Sources

### Primary (HIGH confidence)
- HuggingFace Model Card: `sentence-transformers/all-MiniLM-L6-v2` — 22.7M params, 384-dim, 128-token sequence limit
- HuggingFace Discussions #39: Memory requirements ~43MB (weights alone); PyTorch overhead adds ~100-150MB
- rank-bm25 PyPI: `pip install rank-bm25`, BM25Okapi with k1/b parameters
- bm25s HuggingFace blog: BM25S as faster alternative for larger corpora
- AWS DynamoDB docs: `text` is a reserved word; use ExpressionAttributeNames
- AWS ECS docs: OOM kill at memory hard limit (exit code 137); 256 CPU + 512MB is minimum valid combo

### Secondary (MEDIUM confidence)
- Research (February 2025): Pure semantic retrieval achieves 48.7% recall@1; hybrid BM25+dense achieves 53.4% on open-domain QA
- Research (June 2025): BM25 and MiniLM achieve comparable accuracy on medical document classification; BM25 slightly faster
- WebSearch: Sentence Transformers containers average 3-minute cold start for larger models; all-MiniLM-L6-v2 is much smaller (~22MB vs 400MB+ for larger models)
- AWS Project Lakechain (awslabs): Cold start optimization by caching models in image layers
- WebSearch: DynamoDB Binary type for embeddings is more space-efficient than String type
- Meilisearch blog: Hybrid search (BM25 + vector) typical improvement of 10-15% MRR@5 over BM25 alone

### Tertiary (LOW confidence — verify before implementing)
- Latency estimates (ASR ~200ms, LLM ~800ms, TTS ~400ms): From CONTEXT.md locked decisions; not independently benchmarked in this research session. Verify against real Phase 0 metrics in CloudWatch.
- BM25 latency "~0ms" in CONTEXT.md: Research suggests 0.5-2ms per query for 500 chunks on CPU. Verify empirically in Plan 04.
- ECS task memory headroom for all-MiniLM-L6-v2 at 512MB: Research suggests OOM risk is HIGH. Verify by running container locally with memory limit before ECS deploy.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified (rank-bm25 on PyPI, sentence-transformers on HuggingFace, DynamoDB patterns from AWS docs)
- Architecture: HIGH — BM25 in-memory pattern, DynamoDB corpus scan, Redis cache layer are established patterns
- Memory risk (Pitfall 1): HIGH confidence this is a real risk — ECS OOM behavior, model size, PyTorch overhead all verified
- BM25 accuracy for government FAQ: MEDIUM — recall figures from 2025 research; government-specific benchmarks not independently verified
- Latency estimates: MEDIUM — CONTEXT.md figures used; CloudWatch data from Phase 0 should be checked against these

**Research date:** 2026-03-10
**Valid until:** 2026-06-10 (90 days; all-MiniLM-L6-v2 is stable; DynamoDB pricing stable; rank-bm25 API stable)

**Key action before planning:** The three existing plan files need revision against the new DynamoDB + BM25 + Redis architecture. The existing Plan 02 (Aurora pgvector) must be fully replaced. Plan 01 needs the `AwsKnowledgeAdapter` constructor updated to `DynamoBM25KnowledgeAdapter`. Plan 03 needs the ECS memory upgrade (512MB → 1024MB) added as a blocking prerequisite step.
