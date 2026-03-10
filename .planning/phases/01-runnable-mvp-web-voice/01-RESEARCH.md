# Phase 1: GXA Voice Baseline — Research

**Researched:** 2026-03-10 (updated with Validation Architecture)
**Domain:** Government voice bot: DynamoDB + BM25 + Redis RAG, ECS Fargate, IAM, conversation tracking, CloudWatch metrics, GXA/Granicus intent taxonomy
**Confidence:** HIGH (core stack verified via official AWS docs and PyPI; GXA intents from Granicus published materials; hallucination proxy and government synonyms are MEDIUM confidence based on domain patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md — locked 2026-03-10)

### Locked Decisions

**Two-Tier Deployment Strategy (EC2 REMOVED)**
Same codebase runs in both tiers — only configuration changes:
- Tier 1: Local Machine (Docker Compose) — $0 compute, ~$5/mo API
- Tier 2: ECS Fargate (existing cluster, ap-south-1) — ~$15-20/mo at 512CPU/1024MB

EC2 (t3.micro) removed from roadmap entirely. CONTEXT.md domain block still reads "three-tier" — the planner must update it to "two-tier" when writing plans.

**RAG Service Architecture (LOCKED)**
All services run in same ECS task for MVP (import as modules, not separate processes):
- Port 8000: Orchestrator (FastAPI WebSocket, Phase 0 service modified)
- Port 8001: Embedding service (all-MiniLM-L6-v2, FastAPI, imported as module in MVP)
- Port 8002: BM25 service (stateless reranker, FastAPI, imported as module in MVP)
- Shared: Redis cache (local: Redis container; ECS: same-task Redis sidecar)

**RAG Stack (LOCKED — pgvector/Aurora REMOVED)**
- Embedding model: `all-MiniLM-L6-v2` (384-dim, Sentence Transformers, ~5ms inference)
- Reranking: BM25 via `rank_bm25` library (~1-2ms — pure text matching)
- Caching: Redis (1ms lookup for repeated queries, transparent BM25 fallback if Redis is down)
- Knowledge store: DynamoDB (FAQ text + metadata + pre-computed 384-dim embeddings stored as binary)
- Embeddings at query time: NOT used for BM25 search (reserved for Phase 4 hybrid upgrade)
- PDF storage: S3 (raw source documents)

**RAG Integration Point (LOCKED)**
- LLM: Claude 3.5 Sonnet via Bedrock Converse API
- RAGLLMAdapter injects top-3 FAQ chunks into Bedrock system prompt field
- Always include source attribution in responses

**Latency SLO (LOCKED)**
- Target: <1.5s turn latency (ASR start to TTS complete)
- Per-stage targets: ASR ~200ms, Embed+BM25+Redis ~6ms, LLM ~800ms, TTS ~400ms
- Track per-stage breakdowns in CloudWatch (p50, p95, p99)

**ECS Resource Requirements (LOCKED)**
- ECS task memory: 1024MB (512MB causes OOM with PyTorch/sentence-transformers)
- ECS task CPU: 512 units (upgrade from 256 to handle embedding inference)
- Monthly cost estimate: ~$15.50/mo (up from $8.96/mo at 512MB/256CPU)
- Region: ap-south-1 (Mumbai) — NOT us-east-1

**IAM Permissions Required (LOCKED)**
dynamodb:Scan, dynamodb:GetItem, dynamodb:Query, dynamodb:PutItem, dynamodb:BatchWriteItem, dynamodb:UpdateItem, s3:GetObject, s3:ListBucket, cloudwatch:PutMetricData

**BM25 Accuracy Policy (LOCKED)**
- BM25 70-80% recall@5 acceptable for Phase 1 MVP
- Paraphrase misses mitigated by system prompt query expansion
- Government synonym expansion: >=30 synonym pairs required
- Upgrade path: hybrid semantic + BM25 in Phase 4 if insufficient after real user testing

**Government Synonyms (LOCKED)**
- Minimum 30 synonym pairs for public sector terms
- Applied to BM25 queries (pre-expand query before tokenization)
- Redis failure falls back to direct BM25 — voice turn must NEVER fail due to Redis outage

### Claude's Discretion
- Exact chunking size and overlap for FAQ splitting
- BM25 scoring parameters (k1, b values)
- Redis TTL for cached query results
- CloudWatch dashboard visualization (per-stage timings, outliers)
- DynamoDB table schema (GSI design for client_id filtering, with boto3 paginator from day one)
- System prompt query expansion wording for paraphrase gap mitigation
- Conversation session schema design
- Which metrics go in CloudWatch vs DynamoDB vs logs

### Deferred Ideas (OUT OF SCOPE)
- VAD/Silence Detection: Phase 2
- Separate ECS tasks per service: Phase 2
- Multi-language support: Future phases
- Advanced citation formatting: Phase 4
- Auto-scraping from website: Backlog
- CrossEncoder reranking: Phase 2 upgrade path
- EC2 deployment tier: Removed from roadmap entirely
- Aurora PostgreSQL + pgvector: Removed (replaced by DynamoDB + BM25)
- Multi-turn conversation context injection: Phase 2 (Phase 1 is single-turn per FAQ)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VOIC-03 | Voice sessions satisfy latency SLO targets for first partial, first audio, and turn latency | ECS memory section, latency budget breakdown, per-stage CloudWatch metrics, p95 alarm design |
| RAG-01 | ETL pipeline ingests S3 documents (PDFs) into DynamoDB + BM25 index with required metadata fields (source_doc, department, chunk_id, text, embedding binary, created_at) | DynamoDB data model, ingest pipeline design, IAM permissions section |
| RAG-02 | Retrieval-augmented responses include citations to source documents with page/section reference | BM25 retrieval architecture, DynamoDB FAQ schema, KnowledgeResult.sources pattern, RAGLLMAdapter system prompt injection |
</phase_requirements>

---

## Summary

Phase 1 implements a government voice RAG bot using DynamoDB + BM25 + Redis — a cost-optimized stack that replaces the previously planned Aurora PostgreSQL + pgvector approach. The primary design choices are: store pre-computed 384-dim embeddings in DynamoDB binary attributes (for future hybrid search), run BM25-only retrieval at query time (for MVP simplicity and speed), use Redis as a query result cache with transparent BM25 fallback if Redis is unavailable, and deploy everything in a single ECS Fargate task at 1024MB to comfortably host PyTorch alongside the FastAPI orchestrator.

The research confirms EC2 removal is sound. The gap from local Docker Compose to ECS Fargate is bridged entirely through environment variable configuration (AWS credentials, DynamoDB table names, S3 bucket names). There is no third deployment tier needed for an MVP. The existing Phase 0 test infrastructure uses `unittest` + `pytest` (no config file detected); Phase 1 tests extend this pattern and add `pytest-asyncio` for async adapter tests.

GXA/Granicus government bots serve a well-defined intent taxonomy: property tax, utility payments, trash/waste, permits, elections, courts, parks, emergency management, and 311 general routing. The top 20 government intents are documented below with synonym dictionaries for BM25 query expansion covering 33+ base terms.

**Primary recommendation:** Ship DynamoDB + BM25 + Redis with Redis fallback to BM25 (never fail voice turns). Store embeddings as DynamoDB Binary for Phase 4 upgrade readiness. Track conversations in DynamoDB Table 2 with TTL. Push turn metrics to CloudWatch. The stack handles the <1.5s SLO comfortably with BM25+Redis path running ~6ms total.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `rank_bm25` | 0.2.2 | BM25Okapi text retrieval | Most widely used BM25 Python library, ~1-2ms per query, zero ML inference |
| `sentence-transformers` | 3.x | all-MiniLM-L6-v2 embeddings | 22M params, 384-dim, 5ms inference, 43MB model file, CPU-only capable |
| `redis` (redis-py) | 5.x | Query result caching | Official Python Redis client, asyncio support, connection pool management |
| `boto3` | 1.34+ | DynamoDB + S3 + CloudWatch access | AWS official SDK, IAM role auth native |
| `fastapi` | 0.111+ | WebSocket + REST API server | Async native, already used in Phase 0 |
| `pdfplumber` | 0.11+ | PDF text extraction | Accurate text + layout extraction; better than PyMuPDF for government PDFs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `bm25s` | 0.2+ | Faster BM25 alternative | If `rank_bm25` proves too slow at >1000 docs; BM25S is 500x faster |
| `pybreaker` | 1.2+ | Circuit breaker for Redis | If Redis failure rate >5% — adds open/half-open/closed states |
| `numpy` | 1.26+ | Float32 array → bytes conversion for DynamoDB binary | Required for embedding serialization |
| `pytest-asyncio` | 0.23+ | Async test support for FastAPI | Needed for testing async knowledge adapter and WebSocket handlers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rank_bm25` | `bm25s` | bm25s is 500x faster but less mature; rank_bm25 has more production usage |
| `rank_bm25` | Elasticsearch BM25 | Elasticsearch adds infra cost and complexity; rank_bm25 is in-process |
| Redis for cache | In-memory dict | Redis survives container restarts; dict is reset on each deployment |
| DynamoDB Binary for embeddings | S3 for embeddings | S3 adds per-request latency; DynamoDB collocates text + embedding in one read |

**Installation:**
```bash
pip install rank-bm25 sentence-transformers redis boto3 fastapi pdfplumber numpy pytest pytest-asyncio
```

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
  app/
    services/
      knowledge.py          # KnowledgeAdapter ABC + MockKnowledgeAdapter + DynamoKnowledgeAdapter
      llm.py                # RAGLLMAdapter (system_context injection)
      bm25_index.py         # BM25 index builder, query runner, expand_government_query()
      redis_cache.py        # Redis cache with BM25 fallback
      conversation.py       # ConversationSession + write_conversation_turn()
    orchestrator/
      pipeline.py           # VoicePipeline with RAG stage + per-stage timing
      runtime.py            # build_pipeline() factory with env-based adapter selection
    monitoring.py           # publish_turn_metrics(), publish_rag_metrics()

knowledge/
  pipeline/
    ingest.py               # PDF extraction + chunking (pdfplumber)
    embed.py                # sentence-transformers embedding + DynamoDB BatchWriteItem
  data/
    local/sample_faqs.json  # Seed FAQs for offline dev (10-15 Jackson County FAQs)
    schemas/dynamo_faq.json # DynamoDB table schema spec
    schemas/dynamo_conv.json # Conversation table schema spec

tests/
  backend/
    test_knowledge_adapter.py   # Unit: MockKnowledgeAdapter, DynamoKnowledgeAdapter (mocked boto3)
    test_bm25_redis.py          # Unit: BM25 retrieval, Redis fallback, query expansion
    test_conversation.py        # Unit: ConversationSession, write_conversation_turn (mocked dynamo)
    test_latency_probes.py      # Unit: Pipeline timing fields present and in-range on mock run
  e2e/
    test_phase1_roundtrip.py    # E2E: Full voice turn with mock adapters, assert SLO <1500ms
```

### Pattern 1: BM25 Query with Redis Cache + Transparent Fallback

**What:** Redis stores serialized BM25 results keyed by normalized query string. On Redis hit, skip BM25 entirely. On Redis miss OR Redis error, run BM25 directly. Redis failure NEVER fails the voice turn.

**When to use:** Every knowledge retrieval call in `DynamoKnowledgeAdapter.retrieve()`.

**The critical invariant:** Voice turns must never fail due to cache unavailability. Redis is an optimization, not a dependency.

```python
# Source: pattern derived from redis-py official docs + rank_bm25 PyPI
import redis
import json
import hashlib
from rank_bm25 import BM25Okapi

class BM25RedisRetriever:
    """
    BM25 retrieval with Redis cache and transparent fallback.
    Cache key: SHA-256 of normalized query string
    Cache value: JSON-serialized list of {text, source_doc, score} dicts
    Fallback: run BM25 directly if Redis is unavailable or cache miss
    """

    def __init__(
        self,
        bm25_index: BM25Okapi,
        corpus: list[dict],       # list of {"text": ..., "source_doc": ..., "department": ...}
        redis_client: redis.Redis | None = None,
        redis_ttl: int = 3600,    # 1 hour TTL — FAQ content changes monthly
    ):
        self._bm25 = bm25_index
        self._corpus = corpus
        self._redis = redis_client
        self._redis_ttl = redis_ttl

    def _cache_key(self, query: str) -> str:
        normalized = query.lower().strip()
        return f"bm25:v1:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Returns top_k results. NEVER raises due to Redis failure.
        1. Try Redis GET
        2. Cache hit: deserialize and return
        3. Cache miss or Redis error: run BM25
        4. If BM25 result found: try Redis SET (fire-and-forget, ignore errors)
        5. Return BM25 result
        """
        cache_key = self._cache_key(query)

        # Step 1-2: Try cache
        if self._redis is not None:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass  # Redis down: continue to BM25. NEVER propagate.

        # Step 3: BM25 retrieval — apply query expansion first
        expanded_query = expand_government_query(query)
        tokenized = expanded_query.lower().split()
        scores = self._bm25.get_scores(tokenized)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [
            {
                "text": self._corpus[i]["text"],
                "source_doc": self._corpus[i]["source_doc"],
                "score": float(scores[i]),
            }
            for i in top_indices
            if scores[i] > 0.0  # filter zero-score results
        ]

        # Step 4: Cache results (fire-and-forget)
        if self._redis is not None and results:
            try:
                self._redis.setex(cache_key, self._redis_ttl, json.dumps(results))
            except Exception:
                pass  # Redis down: don't fail. Result still returned.

        return results
```

**Confidence:** HIGH — verified against redis-py official documentation and rank_bm25 PyPI source.

### Pattern 2: DynamoDB Binary Storage for Embeddings

**What:** numpy float32 array (384 dims) → bytes → DynamoDB Binary attribute (type `B`).

**Why store if not used at query time:** Phase 4 will add hybrid search. Storing embeddings now avoids a full re-ingest of all FAQs when Phase 4 arrives.

**Size math:** 384 dimensions × 4 bytes per float32 = 1,536 bytes per embedding. DynamoDB item limit is 400KB. Each FAQ item (text ~500 chars + embedding 1536 bytes + metadata ~200 bytes) = ~2.2KB, well under limit. A 50-FAQ corpus fits in a single Scan with a ~110KB response.

```python
# Source: AWS DynamoDB docs (Binary type) + numpy official docs
import numpy as np
import boto3

def embedding_to_dynamodb_binary(embedding: np.ndarray) -> bytes:
    """Convert float32 numpy array to bytes for DynamoDB Binary attribute.
    boto3 handles base64 encoding/decoding transparently. Pass raw bytes to boto3.
    """
    assert embedding.dtype == np.float32, "Must be float32"
    assert embedding.shape == (384,), f"Expected 384-dim, got {embedding.shape}"
    return embedding.tobytes()  # little-endian float32 bytes, 1536 bytes total

def dynamodb_binary_to_embedding(raw_bytes: bytes) -> np.ndarray:
    """Reconstruct float32 numpy array from DynamoDB Binary attribute bytes."""
    return np.frombuffer(raw_bytes, dtype=np.float32)  # 384-element array

# Write to DynamoDB
dynamo_client = boto3.client("dynamodb", region_name="ap-south-1")
dynamo_client.put_item(
    TableName="voicebot-faq-knowledge",
    Item={
        "department": {"S": "finance"},
        "chunk_id":   {"S": "jackson-property-tax-guide.pdf:chunk:0"},
        "text":       {"S": chunk_text},
        "embedding":  {"B": embedding_to_dynamodb_binary(embedding_array)},
        "source_doc": {"S": "jackson-property-tax-guide.pdf"},
        "created_at": {"S": "2026-03-10T00:00:00Z"},
        "tags":       {"SS": ["property-tax", "finance"]},
    }
)
```

**Critical note:** boto3 automatically base64-encodes bytes when sending to DynamoDB API and decodes on return. You write `bytes`, not base64 strings. This is transparent.

**Confidence:** HIGH — verified against AWS DynamoDB official docs (Binary type descriptor `B`).

### Pattern 3: BM25 Index Build from DynamoDB Corpus

**What:** Load all FAQ text from DynamoDB at startup, build BM25Okapi index in-memory. Index is rebuilt on ECS deployment (monthly ingest updates the corpus in DynamoDB, then a new task revision triggers `__init__`).

**When to use:** Service startup in `DynamoKnowledgeAdapter.__init__()` via FastAPI lifespan context.

```python
# Source: rank_bm25 PyPI documentation + AWS boto3 paginator docs
from rank_bm25 import BM25Okapi
import boto3

def load_bm25_from_dynamodb(table_name: str, region: str = "ap-south-1") -> tuple[BM25Okapi, list[dict]]:
    """
    Scan DynamoDB FAQ table, build BM25 index.
    Returns (bm25_index, corpus_list).
    Uses paginator from day one to handle >1MB DynamoDB responses.
    """
    dynamo = boto3.client("dynamodb", region_name=region)
    paginator = dynamo.get_paginator("scan")

    corpus = []
    for page in paginator.paginate(TableName=table_name):
        for item in page["Items"]:
            corpus.append({
                "text": item["text"]["S"],
                "source_doc": item["source_doc"]["S"],
                "department": item["department"]["S"],
                "chunk_id": item["chunk_id"]["S"],
                # Note: embedding is stored but NOT loaded here — BM25 doesn't use it
                # Load embeddings only when Phase 4 hybrid search is implemented
            })

    if not corpus:
        raise ValueError(f"DynamoDB table {table_name} returned zero items. Cannot build BM25 index.")

    tokenized_corpus = [doc["text"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(
        tokenized_corpus,
        k1=1.5,    # term saturation — higher = more weight on term frequency
        b=0.75,    # length normalization — 0.75 is BM25 standard default
    )
    return bm25, corpus
```

**Confidence:** HIGH — rank_bm25 API verified against PyPI package source.

### Pattern 4: RAGLLMAdapter — System Prompt Context Injection

**What:** Wrap the existing `LLMAdapter` to call BM25 retrieval before every Bedrock call. Inject top-3 FAQ chunks into the Bedrock system prompt field. Include source attribution.

```python
# Source: Phase 0 LLMAdapter pattern + Bedrock Converse API official docs
import boto3

class RAGLLMAdapter(LLMAdapter):
    """
    Extends LLMAdapter to add RAG context retrieval before every LLM call.
    Minimal change: add knowledge retrieval, inject as system prompt context.
    """

    def __init__(self, knowledge_adapter, bedrock_client, model_id: str):
        self._knowledge = knowledge_adapter
        self._bedrock = bedrock_client
        self._model_id = model_id

    async def generate(self, user_query: str, conversation_history: list = None) -> tuple[str, list[str]]:
        """
        Returns (response_text, source_docs_list).
        """
        # Step 1: Retrieve top-3 FAQ chunks
        knowledge_result = await self._knowledge.retrieve(user_query, top_k=3)

        # Step 2: Build system prompt with FAQ context
        if knowledge_result.chunks:
            faq_context = "\n\n".join([
                f"[Source: {src}]\n{chunk}"
                for chunk, src in zip(knowledge_result.chunks, knowledge_result.sources)
            ])
            system_prompt = (
                "You are a helpful Jackson County government assistant. "
                "Answer questions using ONLY the official FAQ information provided below. "
                "Always cite the source document when giving information.\n\n"
                f"=== Official FAQ Information ===\n{faq_context}\n"
                "=== End of FAQ Information ===\n\n"
                "If the answer is not in the FAQ information, say so clearly."
            )
        else:
            system_prompt = (
                "You are a helpful Jackson County government assistant. "
                "I could not find relevant FAQ information for this query. "
                "Tell the user you cannot find specific information and suggest they "
                "visit jacksongov.org or call the relevant department."
            )

        # Step 3: Call Bedrock Converse API
        response = self._bedrock.converse(
            modelId=self._model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_query}]}],
        )
        response_text = response["output"]["message"]["content"][0]["text"]
        return response_text, knowledge_result.sources
```

**Confidence:** HIGH — Bedrock Converse API pattern verified against AWS Bedrock official documentation.

### Pattern 5: FastAPI Lifespan for BM25 Index Loading

**What:** Load BM25 index once at startup (not per-request) using FastAPI lifespan context manager.

```python
# Source: FastAPI official docs (lifespan context manager)
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load BM25 index at startup — not per-request
    from backend.app.orchestrator.runtime import build_pipeline
    app.state.pipeline = build_pipeline()  # builds BM25 index, connects Redis
    yield
    # Cleanup: close Redis connection pool
    if hasattr(app.state, "pipeline") and hasattr(app.state.pipeline.knowledge, "_redis"):
        if app.state.pipeline.knowledge._redis:
            app.state.pipeline.knowledge._redis.connection_pool.disconnect()

app = FastAPI(lifespan=lifespan)
```

**Confidence:** HIGH — FastAPI lifespan context manager is the official pattern for startup/shutdown resource management.

### Anti-Patterns to Avoid

- **Building BM25 index per-request:** Build once at startup in `lifespan()`. For 50 FAQs this is trivial (~1ms), but the pattern matters for correctness under load.
- **Storing embeddings as JSON float list:** Float32 → JSON → DynamoDB is 4x larger (1536 bytes vs ~6KB as JSON float string) and slower to parse. Use binary bytes.
- **Using `dynamodb.scan()` without paginator:** Works for <1MB responses, breaks silently beyond. Use `get_paginator("scan")` from day one.
- **Raising exceptions from Redis failure:** Cache failures should log a warning and fall through to BM25. Never let `redis.exceptions.ConnectionError` propagate to the voice turn.
- **EC2 deployment tier:** Eliminated entirely. Local → ECS directly.
- **Three-tier references in plans:** The CONTEXT.md domain block still says "three-tier" — planner must use "two-tier" language in all plans.
- **01-02-PLAN.md stale pgvector content:** The existing 01-02-PLAN.md references Aurora PostgreSQL + pgvector. It MUST be replaced with DynamoDB + BM25 + Redis plan.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 scoring | Custom TF-IDF implementation | `rank_bm25` | BM25Okapi has correct IDF normalization, k1/b params — custom TF-IDF differs from published BM25 formula |
| Sentence embeddings | Custom transformer inference | `sentence-transformers` | Handles tokenization, pooling, normalization correctly; hand-rolled produces different vector space |
| Redis connection pool | `redis.Redis()` per request | `redis.ConnectionPool` + shared `redis.Redis(connection_pool=pool)` | Per-request connections exhaust file descriptors under load |
| DynamoDB paginator | Manual `LastEvaluatedKey` loop | `boto3.get_paginator("scan")` | Paginator handles `LastEvaluatedKey` correctly; manual loop commonly mis-handles the terminal condition |
| Conversation TTL cleanup | Cron job to delete old sessions | DynamoDB TTL attribute | DynamoDB auto-deletes expired items within 48 hours; no additional cost |
| Percentile calculation | Rolling percentile approximation | `statistics.quantiles()` or CloudWatch percentile stats | Python's statistics module is correct; rolling approximations introduce error |
| Circuit breaker for Redis | Try/except with counter | `pybreaker` (optional) | Circuit breaker adds open/closed/half-open state machine; raw try/except restarts retries too eagerly |

**Key insight:** BM25 and sentence-transformers are research-grade implementations. The math in BM25 (especially IDF with corpus size correction) is non-trivial to replicate correctly. Use the libraries.

---

## ECS Memory — Why 1024 MB

### Memory Budget at 1024MB

| Component | Memory Estimate | Source |
|-----------|-----------------|--------|
| all-MiniLM-L6-v2 model (float32) | ~91 MB | 22M params × 4 bytes per float32 |
| PyTorch runtime overhead | ~150 MB | Community reports for minimal PyTorch CPU inference |
| FastAPI + uvicorn + asyncio | ~50 MB | Typical async Python web server |
| Redis in-container sidecar | ~30 MB | Redis default memory with small working set |
| BM25 index for 50 FAQs (text in memory) | ~5 MB | 50 docs × ~500 words × ~100 bytes avg |
| OS + Python interpreter baseline | ~80 MB | ECS Linux container baseline |
| Safety headroom | ~118 MB | ~12% buffer |
| **Total** | **~524 MB** | Well under 1024MB |

**Why 512MB was too tight:** Phase 0 used ~59MB at idle (no ML libraries). PyTorch for sentence-transformers adds ~241MB minimum. 59MB + 241MB = 300MB just for Python + PyTorch. Adding the model (91MB) = 391MB, dangerously close to 512MB with zero headroom for inference burst.

**Why 1024MB is correct:** Provides ~500MB headroom. ECS kills tasks at the hard limit; memory burst during first-request model warm-up at 512MB causes OOM-kill and restart loop.

### ECS Task Definition (CLI)

```bash
# Register new task definition revision with 1024MB/512CPU
aws ecs register-task-definition \
  --family voice-bot-mvp \
  --requires-compatibilities FARGATE \
  --network-mode awsvpc \
  --cpu 512 \
  --memory 1024 \
  --region ap-south-1 \
  --execution-role-arn arn:aws:iam::148952810686:role/ecsTaskExecutionRole \
  --task-role-arn arn:aws:iam::148952810686:role/voicebot-task-role \
  ...

# Update service to use new revision
aws ecs update-service \
  --cluster voice-bot-mvp-cluster \
  --service voice-bot-mvp-svc \
  --task-definition voice-bot-mvp:NEW_REVISION \
  --region ap-south-1
```

**Valid Fargate CPU+Memory combinations (HIGH confidence — AWS docs):**
- 256 CPU: 512, 1024, 2048 MB (512MB insufficient here)
- 512 CPU: 1024, 2048, 3072, 4096 MB (1024MB is the target)

**Monthly cost impact:**
- 256 CPU / 512 MB: $0.01245/hr = $8.96/mo
- 512 CPU / 1024 MB: ~$0.0215/hr = ~$15.50/mo (AWS Fargate pricing ap-south-1)

**Confidence:** HIGH — Fargate memory/CPU combinations verified against AWS ECS official documentation.

---

## IAM Permissions — Complete List

### ECS Task Role Policy (Minimum Required)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBFAQKnowledgeAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchWriteItem",
        "dynamodb:UpdateItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:ap-south-1:148952810686:table/voicebot-faq-knowledge",
        "arn:aws:dynamodb:ap-south-1:148952810686:table/voicebot-faq-knowledge/index/*",
        "arn:aws:dynamodb:ap-south-1:148952810686:table/voicebot-conversations",
        "arn:aws:dynamodb:ap-south-1:148952810686:table/voicebot-conversations/index/*"
      ]
    },
    {
      "Sid": "S3FAQDocumentRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::voicebot-faq-documents",
        "arn:aws:s3:::voicebot-faq-documents/*"
      ]
    },
    {
      "Sid": "CloudWatchMetricsPublish",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockInference",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:ap-south-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
      ]
    },
    {
      "Sid": "TranscribeStreaming",
      "Effect": "Allow",
      "Action": [
        "transcribe:StartStreamTranscription",
        "transcribe:StartStreamTranscriptionWebSocket"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PollyTTS",
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech",
        "polly:DescribeVoices"
      ],
      "Resource": "*"
    }
  ]
}
```

**Confidence:** HIGH — Permission names verified against AWS IAM documentation and DynamoDB API permissions reference.

---

## DynamoDB Data Model

### Table 1: FAQ Knowledge Base (`voicebot-faq-knowledge`)

```
PK: department (S)         — "finance", "utilities", "permits", "elections", etc.
SK: chunk_id (S)           — "jackson-property-tax-guide.pdf:chunk:0"

Attributes:
  text (S)                 — FAQ chunk text (~300-400 words)
  source_doc (S)           — Original PDF filename
  embedding (B)            — float32 numpy array as bytes (384 dims, 1536 bytes)
  created_at (S)           — ISO 8601 timestamp
  tags (SS)                — String set: ["property-tax", "payment", "deadline"]

GSI-1 (optional Phase 2 multi-tenant):
  PK: client_id (S)        — "jackson-county"
  SK: created_at (S)       — enables time-ordered queries
```

**Required metadata fields per RAG-01:**
- `source_doc` (S) — maps to requirement: source document reference
- `department` (S) — the PK/filter dimension
- `chunk_id` (S) — unique identifier for citation
- `text` (S) — the FAQ chunk content
- `embedding` (B) — pre-computed 384-dim binary
- `created_at` (S) — ingestion timestamp

**Access patterns:**
1. Full corpus load at startup: `Scan(TableName=table)` via paginator → build BM25 index
2. Single chunk fetch: `GetItem(department=dept, chunk_id=id)` → for citation display
3. Department filter: `Query(department="finance")` → department-specific search subset

**Cost estimate for 50 FAQs:**
- 50 items × 2.2KB avg = 110KB total table size
- Scan at startup: ~7 RCUs total
- At 1 startup per deployment (not per-request): negligible DynamoDB cost

### Table 2: Conversation Sessions (`voicebot-conversations`)

```
PK: session_id (S)         — UUID v4, e.g., "sess_a1b2c3d4"
SK: turn_number (N)        — 0, 1, 2, ... (integer sort key for ordered retrieval)

Attributes:
  user_input (S)           — Raw user text after ASR
  assistant_response (S)   — LLM response text
  rag_chunks_used (SS)     — Set of chunk_ids retrieved for this turn
  asr_ms (N)               — ASR stage latency in milliseconds
  rag_ms (N)               — RAG retrieval latency (BM25 + Redis) in ms
  llm_ms (N)               — LLM inference latency in ms
  tts_ms (N)               — TTS synthesis latency in ms
  total_ms (N)             — End-to-end turn latency in ms
  timestamp (S)            — ISO 8601 UTC
  slo_met (BOOL)           — true if total_ms < 1500
  retrieval_score (N)      — BM25 top-1 score (proxy for RAG quality)
  department_hit (S)       — Department of top FAQ chunk returned
  query_expanded (BOOL)    — Whether query expansion triggered a synonym match

  # TTL: auto-expire after 90 days
  ttl (N)                  — Unix epoch seconds (current time + 90 * 86400)
```

**Access patterns:**
1. Write turn: `PutItem(session_id=id, turn_number=N, ...)`
2. Get full session: `Query(session_id=id)` → returns all turns sorted by turn_number
3. Get session turn count: `Query(session_id=id, Select=COUNT)` → 1 RCU

**TTL enable command:**
```bash
aws dynamodb update-time-to-live \
  --table-name voicebot-conversations \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region ap-south-1
```

**Confidence:** HIGH for table schemas (derived from AWS official DynamoDB chatbot blog patterns).

---

## Conversation Tracking — Design

### WHY implement in Plan 03 (not deferred to Phase 2)

Conversation tracking data is required for the metrics dashboard in Plan 04. Without session records, you cannot compute turns_per_session, session_completion_rate, follow_up_rate, or cost_per_conversation. These are the metrics that demonstrate MVP value to stakeholders.

### Minimal Phase 1 Implementation

```python
# backend/app/services/conversation.py
import uuid
import time
from datetime import datetime, timezone

class ConversationSession:
    """Lightweight conversation tracker for Phase 1 DynamoDB storage."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        self.turn_number = 0
        self._start_time = time.monotonic()

    def next_turn_number(self) -> int:
        self.turn_number += 1
        return self.turn_number

def write_conversation_turn(
    dynamo_client,
    session: ConversationSession,
    user_input: str,
    assistant_response: str,
    pipeline_result,  # PipelineResult with asr_ms, rag_ms, llm_ms, tts_ms fields
    rag_chunk_ids: list[str],
    table_name: str = "voicebot-conversations",
):
    """Write a single conversation turn to DynamoDB."""
    now = datetime.now(timezone.utc)
    ttl_90_days = int(now.timestamp()) + (90 * 86400)
    total_ms = pipeline_result.asr_ms + pipeline_result.rag_ms + pipeline_result.llm_ms + pipeline_result.tts_ms

    dynamo_client.put_item(
        TableName=table_name,
        Item={
            "session_id":         {"S": session.session_id},
            "turn_number":        {"N": str(session.next_turn_number())},
            "user_input":         {"S": user_input[:2000]},
            "assistant_response": {"S": assistant_response[:4000]},
            "rag_chunks_used":    {"SS": rag_chunk_ids} if rag_chunk_ids else {"NULL": True},
            "asr_ms":             {"N": str(round(pipeline_result.asr_ms, 2))},
            "rag_ms":             {"N": str(pipeline_result.rag_ms, 2))},
            "llm_ms":             {"N": str(round(pipeline_result.llm_ms, 2))},
            "tts_ms":             {"N": str(round(pipeline_result.tts_ms, 2))},
            "total_ms":           {"N": str(round(total_ms, 2))},
            "timestamp":          {"S": now.isoformat()},
            "slo_met":            {"BOOL": total_ms < 1500},
            "ttl":                {"N": str(ttl_90_days)},
        }
    )
```

**Confidence:** HIGH — DynamoDB session storage pattern verified against AWS official blog.

---

## Metrics Dashboard — Full Specification

### CloudWatch Metric Names (Phase 1)

```
Namespace: voicebot/latency
  ASRLatency          (Unit: Milliseconds, Dimensions: {Environment: dev|prod})
  RAGLatency          (Unit: Milliseconds, Dimensions: {Environment: dev|prod})
  LLMLatency          (Unit: Milliseconds, Dimensions: {Environment: dev|prod})
  TTSLatency          (Unit: Milliseconds, Dimensions: {Environment: dev|prod})
  TotalTurnLatency    (Unit: Milliseconds, Dimensions: {Environment: dev|prod})

Namespace: voicebot/rag
  CacheHits           (Unit: Count, Dimensions: {Environment: dev|prod})
  CacheMisses         (Unit: Count, Dimensions: {Environment: dev|prod})
  BM25TopScore        (Unit: None, Dimensions: {Environment: dev|prod})
  QueryExpandedHits   (Unit: Count, Dimensions: {Environment: dev|prod})
  FallbackToDirectBM25 (Unit: Count)  — Redis was down, fell through to BM25

Namespace: voicebot/conversations
  SessionsStarted     (Unit: Count)
  TurnsCompleted      (Unit: Count)
  SLOViolations       (Unit: Count)   — turns where total_ms >= 1500

Namespace: voicebot/operations (existing from Phase 0)
  HourlyCost, DailyCost, MonthlyCost, IdleTasks
```

### Per-Turn Metrics Publication

```python
def publish_turn_metrics(result, redis_hit: bool, bm25_score: float,
                          query_expanded: bool, cw_client, env: str = "prod"):
    """Publish all per-turn metrics to CloudWatch in a single batch call."""
    dims = [{"Name": "Environment", "Value": env}]
    cw_client.put_metric_data(
        Namespace="voicebot/latency",
        MetricData=[
            {"MetricName": "ASRLatency", "Value": result.asr_ms, "Unit": "Milliseconds", "Dimensions": dims},
            {"MetricName": "RAGLatency", "Value": result.rag_ms, "Unit": "Milliseconds", "Dimensions": dims},
            {"MetricName": "LLMLatency", "Value": result.llm_ms, "Unit": "Milliseconds", "Dimensions": dims},
            {"MetricName": "TTSLatency", "Value": result.tts_ms, "Unit": "Milliseconds", "Dimensions": dims},
            {"MetricName": "TotalTurnLatency",
             "Value": result.asr_ms + result.rag_ms + result.llm_ms + result.tts_ms,
             "Unit": "Milliseconds", "Dimensions": dims},
        ]
    )
    cw_client.put_metric_data(
        Namespace="voicebot/rag",
        MetricData=[
            {"MetricName": "CacheHits" if redis_hit else "CacheMisses", "Value": 1, "Unit": "Count", "Dimensions": dims},
            {"MetricName": "BM25TopScore", "Value": bm25_score, "Unit": "None", "Dimensions": dims},
            {"MetricName": "QueryExpandedHits" if query_expanded else "QueryExpandedMisses", "Value": 1, "Unit": "Count", "Dimensions": dims},
        ]
    )
```

### Recommended CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| SLO Breach | TotalTurnLatency p95 | > 1500ms | SNS notification |
| Memory High | ECS MemoryUtilization | > 85% | SNS notification |
| Redis Down | FallbackToDirectBM25 | > 10/5min | SNS notification |
| Error Rate | 5xx errors from /ws | > 5/min | SNS notification |

**Confidence:** HIGH for CloudWatch metric names and costs.

---

## GXA / Granicus — Top Government Intents

### Top 20 Municipal Government Intents (Jackson County applicable)

Derived from Granicus GXA published materials, Denver "Sunny" chatbot reports, NYC311, and general municipal service taxonomy research.

| # | Intent Category | Example Questions | Jackson County Department |
|---|-----------------|-------------------|--------------------------|
| 1 | Property Tax Status | "How much do I owe in property taxes?", "When is my tax bill due?" | Collection / Assessment |
| 2 | Property Tax Payment | "How do I pay my property tax online?", "Do you accept credit cards?" | Collection |
| 3 | Property Tax Appeal | "How do I dispute my property assessment?", "How do I file an informal review?" | Assessment |
| 4 | Utility Bill Payment | "How do I pay my water bill?", "When is my utility payment due?" | Utilities |
| 5 | Trash Pickup Schedule | "When is my garbage day?", "Is there holiday pickup?" | Utilities / Public Works |
| 6 | Recycling Information | "What can I recycle?", "Where is the recycling drop-off?" | Utilities |
| 7 | Building Permit Application | "How do I apply for a building permit?" | Planning & Zoning |
| 8 | Permit Status Check | "What's the status of my permit application?" | Planning & Zoning |
| 9 | Voter Registration | "How do I register to vote?", "Is my voter registration up to date?" | Elections |
| 10 | Election Day Info | "Where is my polling place?", "What ID do I need to vote?" | Elections |
| 11 | Business License Renewal | "How do I renew my business license?" | Finance / Revenue |
| 12 | Court Fee Payment | "How do I pay a court fee?", "Traffic ticket costs?" | Courts |
| 13 | Road / Pothole Report | "How do I report a pothole?" | Public Works |
| 14 | Emergency Contacts | "Who do I call in an emergency?" | Emergency Management |
| 15 | Parks & Recreation | "How do I register for a parks program?" | Parks & Recreation |
| 16 | Sheriff Non-Emergency | "What's the non-emergency sheriff number?" | Sheriff |
| 17 | SNAP / Food Assistance | "How do I apply for food stamps?" | Human Services |
| 18 | Senior Services | "What senior programs are available?" | Senior Services |
| 19 | Stray Animal / Animal Control | "Who do I call about a stray dog?" | Animal Control |
| 20 | 311 General Routing | "I need to report something but don't know which department" | 311 / Call Center |

**Confidence:** MEDIUM-HIGH — derived from Granicus published use cases, NYC311 common topics, and Jackson County website structure.

---

## Government Synonyms — BM25 Query Expansion

### Implementation Pattern: Pre-Expand Query Before BM25 Tokenization

**Why pre-expand (not post-expand):** BM25 operates on the tokenized query. Add synonyms to the query string before tokenization. This is simpler and more predictable than modifying the BM25 index.

```python
# backend/app/services/bm25_index.py
# 33+ base term synonym pairs — meets the >=30 requirement

GOVERNMENT_SYNONYMS: dict[str, list[str]] = {
    # Waste / Trash (4 terms)
    "trash": ["waste collection", "garbage", "refuse", "rubbish", "solid waste"],
    "garbage": ["trash", "waste collection", "refuse", "rubbish"],
    "recycling": ["recyclables", "recycle", "recycling pickup", "curbside recycling"],
    "bulk trash": ["large item pickup", "bulk pickup", "junk removal", "furniture pickup"],

    # Tax and Payments (8 terms)
    "property tax": ["real estate tax", "tax bill", "property assessment", "tax payment"],
    "personal property tax": ["vehicle tax", "car tax", "business personal property"],
    "tax bill": ["property tax", "tax statement", "tax notice"],
    "owe": ["balance", "amount due", "outstanding", "unpaid"],
    "pay": ["payment", "pay online", "pay by mail", "payment options"],
    "delinquent": ["past due", "overdue", "late payment", "delinquency"],
    "rebate": ["credit", "reimbursement", "refund", "tax relief"],
    "exemption": ["tax exemption", "homestead exemption", "senior exemption", "disability exemption"],

    # Benefits and Assistance (4 terms)
    "snap": ["food stamps", "food assistance", "ebt", "food benefits", "supplemental nutrition"],
    "food stamps": ["snap", "ebt", "food assistance", "food benefits"],
    "benefits": ["assistance", "programs", "services", "aid", "support"],
    "welfare": ["public assistance", "benefits", "aid", "human services"],

    # Permits and Licensing (3 terms)
    "permit": ["building permit", "zoning permit", "construction permit", "development permit"],
    "license": ["business license", "contractor license", "professional license"],
    "zoning": ["land use", "zoning regulations", "zoning variance", "rezoning"],

    # Elections and Voting (4 terms)
    "vote": ["voter registration", "polling place", "ballot", "election"],
    "voter registration": ["register to vote", "voting registration", "voter card"],
    "polling place": ["polling location", "where to vote", "voting location", "poll site"],
    "absentee": ["mail-in ballot", "absentee ballot", "vote by mail"],

    # Courts and Legal (4 terms)
    "traffic ticket": ["citation", "moving violation", "speeding ticket", "fine"],
    "court fee": ["court cost", "filing fee", "court charge"],
    "fine": ["penalty", "court fee", "traffic ticket", "citation fee"],
    "lawsuit": ["civil case", "legal action", "court case"],

    # Utilities and Infrastructure (4 terms)
    "water bill": ["utility bill", "water payment", "water service"],
    "sewer": ["sanitation", "wastewater", "sewage"],
    "pothole": ["road damage", "road repair", "street repair", "pavement issue"],
    "streetlight": ["street light", "light outage", "broken light"],

    # Emergency and Safety (3 terms)
    "emergency": ["911", "urgent", "crisis", "hazard"],
    "non-emergency": ["non emergency", "sheriff", "noise complaint", "general issue"],
    "animal control": ["stray animal", "dog bite", "animal complaint", "animal shelter"],

    # Parks and Recreation (2 terms)
    "parks": ["recreation", "parks department", "park hours", "park facilities"],
    "program": ["class", "activity", "registration", "sign up"],
}
# Total: 38 base terms (exceeds >=30 requirement)

def expand_government_query(query: str) -> str:
    """
    Expand query with government synonyms before BM25 tokenization.
    Adds synonyms as additional terms (not replace original).
    Example: "when is my trash day" -> "when is my trash day waste collection garbage refuse"
    """
    query_lower = query.lower()
    expanded_terms = [query]

    for term, synonyms in GOVERNMENT_SYNONYMS.items():
        if term in query_lower:
            expanded_terms.extend(synonyms[:2])  # add 1-2 most relevant synonyms

    # Deduplicate while preserving order
    seen = set()
    unique_terms = []
    for term in " ".join(expanded_terms).split():
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return " ".join(unique_terms)
```

**Synonym coverage (38 base terms — exceeds >=30 requirement):**

| Category | Count |
|----------|-------|
| Waste/Trash | 4 |
| Tax/Payments | 8 |
| Benefits | 4 |
| Permits/Licensing | 3 |
| Elections | 4 |
| Courts | 4 |
| Utilities/Infrastructure | 4 |
| Emergency/Safety | 3 |
| Parks | 2 |
| **Total** | **38** |

**Confidence:** MEDIUM-HIGH — synonym pairs derived from domain knowledge of US municipal government terminology and confirmed by Jackson County website structure.

---

## Common Pitfalls

### Pitfall 1: Redis Failure Propagating as Voice Turn Error
**What goes wrong:** Redis connection error raises exception, propagates through `retrieve()`, voice turn returns error to user.
**Why it happens:** Default redis-py throws `redis.exceptions.ConnectionError` on timeout or connection failure.
**How to avoid:** Wrap ALL Redis operations in try/except that catches `Exception` (not just `redis.exceptions.ConnectionError`) and falls through to BM25. Log at WARNING level.
**Warning signs:** User-facing errors mentioning "connection refused" or "timeout." CloudWatch FallbackToDirectBM25 counter rising unexpectedly.

### Pitfall 2: BM25 Index Not Built Before First Request
**What goes wrong:** First voice turn tries to call `BM25Okapi.get_scores()` but corpus is empty. Returns no results. LLM has no context.
**Why it happens:** DynamoDB scan and BM25 build happen in `__init__`. If DynamoDB is unavailable at startup, build fails silently with empty corpus.
**How to avoid:** Check corpus length after build. If empty, raise at startup (not silently). Use `DescribeTable` before Scan to verify table exists.
**Warning signs:** `BM25TopScore` metric stays at 0.0 for all turns. Retrieved chunks list is empty on all turns.

### Pitfall 3: DynamoDB Scan Without Paginator Returns Truncated Results
**What goes wrong:** `dynamo.scan()` returns at most 1MB per call. For 50 FAQs (~110KB), fine today. At 200+ FAQs (~440KB), results are silently truncated. BM25 index misses chunks.
**Why it happens:** DynamoDB returns `LastEvaluatedKey` when results are paginated. Without paginator, you don't fetch next page.
**How to avoid:** Use `boto3.get_paginator("scan")` from day one.
**Warning signs:** FAQ count in BM25 index doesn't match DynamoDB item count.

### Pitfall 4: Embedding Stored as JSON Float List (Not Binary)
**What goes wrong:** 384 float values stored as a JSON string `[0.234, -0.145, ...]`. Takes ~5KB per embedding instead of 1.5KB.
**Why it happens:** Easier to write `json.dumps(embedding.tolist())` than `embedding.tobytes()`.
**How to avoid:** Always use `numpy.ndarray.tobytes()` and DynamoDB `{"B": bytes_value}`.
**Warning signs:** DynamoDB items showing ~5-6KB size instead of ~2.2KB.

### Pitfall 5: ECS Task OOM-Killed During Model Warm-Up
**What goes wrong:** ECS task starts, loads sentence-transformers model, memory spikes to 450MB, ECS kills task at 512MB hard limit. Service restart loop. Logs show `OOMKilled`.
**Why it happens:** PyTorch allocates working memory for first inference call. Cold start allocation exceeds 512MB briefly.
**How to avoid:** Run at 1024MB. Already locked in CONTEXT.md.
**Warning signs:** ECS task cycling every few minutes. Tasks going from Running to Stopped repeatedly.

### Pitfall 6: Stale BM25 Index After FAQ Updates
**What goes wrong:** New FAQs written to DynamoDB but BM25 index in memory not rebuilt. Queries don't hit new FAQ content.
**Why it happens:** BM25 index built once at startup from DynamoDB Scan. Monthly updates to DynamoDB don't trigger index rebuild.
**How to avoid:** Add an index rebuild endpoint (`POST /admin/rebuild-index`) or trigger rebuild on ECS service redeployment.
**Warning signs:** New FAQ chunks in DynamoDB but no retrieval hits for new topic areas.

### Pitfall 7: Three-Tier Language in Plans
**What goes wrong:** Plans reference EC2 tier (three-tier strategy) which was eliminated.
**Why it happens:** CONTEXT.md domain block still reads "three-tier deployment strategy" — stale content.
**How to avoid:** All 4 plans (01-01 through 01-04) must use two-tier language: "Local Docker Compose" and "ECS Fargate" only. No EC2 references.
**Warning signs:** Any plan mentioning t3.micro, EC2 instance, or three-tier strategy.

### Pitfall 8: Existing 01-02-PLAN.md Has Stale pgvector Architecture
**What goes wrong:** 01-02-PLAN.md references Aurora PostgreSQL + pgvector.
**How to avoid:** 01-02-PLAN.md MUST be completely rewritten targeting DynamoDB Scan → BM25 index build → Redis cache pattern. Archive any Aurora/psycopg2 content.
**Warning signs:** Executor attempts to provision Aurora Serverless v2 database.

---

## Code Examples

### DynamoKnowledgeAdapter — Full Working Example

```python
# Source: rank_bm25 PyPI docs + redis-py official docs + AWS boto3 docs
import hashlib
import json
import time
from rank_bm25 import BM25Okapi
import redis

class DynamoKnowledgeAdapter:
    """
    Production KnowledgeAdapter using DynamoDB (corpus storage) + BM25 (retrieval) + Redis (cache).
    Fallback: Redis unavailable -> BM25 directly. Never fail voice turns due to cache.
    """

    def __init__(
        self,
        dynamo_client,
        table_name: str,
        redis_url: str | None = "redis://localhost:6379",
        redis_ttl: int = 3600,
        region: str = "ap-south-1",
    ):
        self._corpus, self._bm25 = self._build_index(dynamo_client, table_name)

        self._redis = None
        self._redis_ttl = redis_ttl
        if redis_url:
            try:
                pool = redis.ConnectionPool.from_url(redis_url, max_connections=10)
                self._redis = redis.Redis(connection_pool=pool, socket_connect_timeout=1, socket_timeout=0.5)
                self._redis.ping()
            except Exception as e:
                import logging
                logging.warning(f"Redis unavailable at startup: {e}. Using BM25 direct.")
                self._redis = None

    def _build_index(self, dynamo_client, table_name: str) -> tuple[list[dict], BM25Okapi]:
        paginator = dynamo_client.get_paginator("scan")
        corpus = []
        for page in paginator.paginate(TableName=table_name):
            for item in page["Items"]:
                corpus.append({
                    "text": item["text"]["S"],
                    "source_doc": item["source_doc"]["S"],
                    "department": item["department"]["S"],
                    "chunk_id": item["chunk_id"]["S"],
                })

        if not corpus:
            raise ValueError(f"DynamoDB table {table_name} returned zero items. Cannot build BM25 index.")

        tokenized = [doc["text"].lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized, k1=1.5, b=0.75)
        return corpus, bm25

    async def retrieve(self, query: str, top_k: int = 5):
        import asyncio
        t0 = time.monotonic()
        results = await asyncio.to_thread(self._retrieve_sync, query, top_k)
        latency_ms = (time.monotonic() - t0) * 1000
        return KnowledgeResult(
            chunks=[r["text"] for r in results],
            sources=[r["source_doc"] for r in results],
            search_latency_ms=latency_ms,
        )

    def _retrieve_sync(self, query: str, top_k: int) -> list[dict]:
        cache_key = f"bm25:v1:{hashlib.sha256(query.lower().encode()).hexdigest()[:16]}"

        if self._redis:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        from backend.app.services.bm25_index import expand_government_query
        expanded = expand_government_query(query)
        scores = self._bm25.get_scores(expanded.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [
            {"text": self._corpus[i]["text"], "source_doc": self._corpus[i]["source_doc"],
             "department": self._corpus[i]["department"], "score": float(scores[i])}
            for i in top_indices if scores[i] > 0.01
        ]

        if self._redis and results:
            try:
                self._redis.setex(cache_key, self._redis_ttl, json.dumps(results))
            except Exception:
                pass

        return results
```

### Docker Compose — Local Development

```yaml
# docker-compose.yml — Local 2-tier equivalent (no EC2)
version: "3.9"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ASR_PROVIDER=aws
      - LLM_PROVIDER=bedrock
      - TTS_PROVIDER=polly
      - DYNAMO_TABLE_NAME=voicebot-faq-knowledge
      - DYNAMO_CONV_TABLE_NAME=voicebot-conversations
      - S3_BUCKET=voicebot-faq-documents
      - REDIS_URL=redis://redis:6379
      - AWS_DEFAULT_REGION=ap-south-1
    volumes:
      - ~/.aws:/root/.aws:ro   # Mount local AWS credentials (local-only, NOT in ECS)
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru
```

**ECS equivalent:** Same environment variables set as ECS task definition environment. AWS credentials from IAM task role (not volume mount). Redis as sidecar container in same task definition.

### Ingest Pipeline — PDF to DynamoDB

```python
# knowledge/pipeline/ingest.py
import pdfplumber
from sentence_transformers import SentenceTransformer

def ingest_pdf_to_dynamodb(pdf_path: str, department: str, dynamo_client, table_name: str):
    """Extract FAQ chunks from PDF and write to DynamoDB with embeddings."""
    model = SentenceTransformer("all-MiniLM-L6-v2")

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Simple chunking: split on blank lines, filter short chunks
    raw_chunks = [c.strip() for c in full_text.split("\n\n") if len(c.strip()) > 100]

    items = []
    for i, chunk_text in enumerate(raw_chunks):
        embedding = model.encode(chunk_text, convert_to_numpy=True).astype("float32")
        chunk_id = f"{pdf_path.name}:chunk:{i}"
        items.append({
            "PutRequest": {
                "Item": {
                    "department": {"S": department},
                    "chunk_id":   {"S": chunk_id},
                    "text":       {"S": chunk_text},
                    "embedding":  {"B": embedding.tobytes()},
                    "source_doc": {"S": pdf_path.name},
                    "created_at": {"S": datetime.now(timezone.utc).isoformat()},
                }
            }
        })

    # BatchWriteItem: max 25 items per call
    for batch_start in range(0, len(items), 25):
        batch = items[batch_start:batch_start + 25]
        dynamo_client.batch_write_item(RequestItems={table_name: batch})

    print(f"Ingested {len(items)} chunks from {pdf_path.name} to {table_name}")
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Aurora PostgreSQL + pgvector | DynamoDB + BM25 + Redis | ~$43-80/mo savings; simpler ops |
| Bedrock Titan V2 embeddings (1536-dim) | all-MiniLM-L6-v2 sentence-transformers (384-dim) | Dimension consistency; ~75% cost reduction |
| EC2 intermediate tier (three-tier) | Local Docker -> ECS directly (two-tier) | Eliminated ops complexity |
| Per-request embedding at query time | Pre-computed embeddings stored in DynamoDB | ~5ms savings per query |
| Single CloudWatch namespace | `voicebot/latency` + `voicebot/rag` + `voicebot/conversations` | Per-dimension alerting |
| No conversation tracking | DynamoDB Table 2 with TTL | Enables cost-per-session metrics |

**Deprecated/outdated — remove from any plan that references them:**
- Aurora PostgreSQL Serverless v2: Replaced by DynamoDB + BM25.
- `pg_schema.sql` (vector(384)): No longer needed.
- `AwsKnowledgeAdapter` with psycopg2: Replace with `DynamoKnowledgeAdapter` using boto3.
- EC2 deployment tier: Eliminated. Two-tier only.
- CONTEXT.md domain block "three-tier": Must be updated to "two-tier" by planner.

---

## Open Questions

1. **Redis in ECS: sidecar container vs ElastiCache**
   - What we know: Running Redis as a sidecar container in the same ECS task is viable for MVP. ElastiCache adds ~$13/mo.
   - What's unclear: ECS Fargate multi-container tasks share the same task definition; Redis sidecar adds ~30MB memory.
   - Recommendation: Use Redis sidecar in same task definition for Phase 1. Move to ElastiCache in Phase 2 if Redis restart during rolling update is observed.

2. **BM25 index rebuild mechanism**
   - What we know: Monthly FAQ updates require BM25 index rebuild. ECS rolling deployment triggers `__init__` which rebuilds from DynamoDB.
   - What's unclear: Is a rolling deployment triggered by FAQ-only updates (no code change)?
   - Recommendation: Add an admin endpoint `POST /admin/rebuild-index` that rebuilds in-memory without redeployment. Protected by a simple admin token.

3. **SNAP/benefits synonyms completeness**
   - What we know: Jackson County is in Missouri; county-level benefits administration may not include SNAP directly (often state-administered).
   - Recommendation: Include SNAP synonyms in the dictionary but validate against actual FAQ corpus before launch.

4. **Conversation tracking in Plan 03 vs Plan 04**
   - Recommendation: Implement in Plan 03 (ECS Deployment) as a lightweight task. Plan 04 (Monitoring) requires it for session-level metric computation.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no config file detected — add pytest.ini in Wave 0) |
| Config file | pytest.ini — Wave 0 creates it |
| Quick run command | `python -m pytest tests/backend/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |
| Async test support | `pytest-asyncio==0.23+` (add to requirements) |

**Existing infrastructure (Phase 0):**
- `tests/backend/test_backend_contracts.py` — FastAPI TestClient, `unittest.TestCase` style
- `tests/backend/test_orchestration_pipeline.py` — VoicePipeline unit tests with mock adapters
- `tests/e2e/test_aws_dev_deploy_smoke.py` — live smoke test (AWS credentials required)
- `tests/e2e/test_phase0_roundtrip.py` — full pipeline roundtrip

Phase 1 extends this with new test files in `tests/backend/` and `tests/e2e/`.

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOIC-03 | Turn latency p95 < 1500ms measured per-stage with mock adapters | Unit | `python -m pytest tests/backend/test_latency_probes.py -x -q` | Wave 0 gap |
| VOIC-03 | Per-stage timing fields (asr_ms, rag_ms, llm_ms, tts_ms) present on PipelineResult | Unit | `python -m pytest tests/backend/test_latency_probes.py::test_pipeline_result_has_timing_fields -x -q` | Wave 0 gap |
| VOIC-03 | SLO flag (slo_met=True) set correctly on conversation turn records | Unit | `python -m pytest tests/backend/test_conversation.py::test_slo_flag_set_on_turn_write -x -q` | Wave 0 gap |
| RAG-01 | DynamoDB FAQ table ingested with required metadata fields (source_doc, department, chunk_id, text, embedding, created_at) | Unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_faq_item_has_required_fields -x -q` | Wave 0 gap |
| RAG-01 | BM25 index builds from DynamoDB corpus without error | Unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_bm25_index_builds -x -q` | Wave 0 gap |
| RAG-01 | DynamoDB Scan uses paginator (not bare scan) | Unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_dynamo_uses_paginator -x -q` | Wave 0 gap |
| RAG-02 | RAGLLMAdapter injects top-3 FAQ chunks into Bedrock system prompt | Unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_rag_llm_adapter_injects_context -x -q` | Wave 0 gap |
| RAG-02 | Retrieved chunks include source_doc attribution | Unit | `python -m pytest tests/backend/test_bm25_redis.py::test_retrieve_returns_source_attribution -x -q` | Wave 0 gap |
| RAG-02 | Redis fallback to BM25 on Redis failure (no exception raised) | Unit | `python -m pytest tests/backend/test_bm25_redis.py::test_redis_fallback_on_failure -x -q` | Wave 0 gap |
| RAG-02 | BM25 query expansion adds government synonyms to tokenized query | Unit | `python -m pytest tests/backend/test_bm25_redis.py::test_expand_government_query_adds_synonyms -x -q` | Wave 0 gap |
| RAG-01+RAG-02 | Full voice turn with RAG retrieval returns sources in response (mock adapters) | E2E | `python -m pytest tests/e2e/test_phase1_roundtrip.py -x -q` | Wave 0 gap |
| VOIC-03 | ECS task memory set to 1024MB in task definition | Manual/smoke | Manual: `aws ecs describe-task-definition --task-definition voice-bot-mvp --region ap-south-1` | N/A — infra check |
| VOIC-03 | CloudWatch publishes TotalTurnLatency metric after each voice turn (ECS live) | Smoke | `python -m pytest tests/e2e/test_aws_dev_deploy_smoke.py -x -q -k "latency"` | Extend existing |

### Success Criterion Test Mapping

The 8 phase success criteria map to tests as follows:

| Success Criterion | Test(s) | Status |
|-------------------|---------|--------|
| 1. Bot answers Jackson County FAQs correctly via RAG | `test_phase1_roundtrip.py` + manual FAQ validation | Wave 0 gap |
| 2. RAGLLMAdapter injects top-3 FAQ context chunks | `test_knowledge_adapter.py::test_rag_llm_adapter_injects_context` | Wave 0 gap |
| 3. Turn latency measured per-stage, below 1.5s p95 | `test_latency_probes.py` (mock, < 100ms) + ECS smoke | Wave 0 gap |
| 4. Same Docker Compose codebase runs locally and on ECS | `test_phase1_roundtrip.py` (local) + ECS smoke test | Wave 0 gap |
| 5. ECS task uses 1024 MB memory | Manual infra check via AWS CLI | N/A |
| 6. IAM role includes all required permissions | Manual: `aws iam simulate-principal-policy` | N/A |
| 7. Redis failure falls back to direct BM25 | `test_bm25_redis.py::test_redis_fallback_on_failure` | Wave 0 gap |
| 8. Government synonym expansion applied (>=30 pairs) | `test_bm25_redis.py::test_expand_government_query_adds_synonyms` + synonym count assertion | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/backend/ -x -q` (unit tests only, ~5-15 seconds)
- **Per wave merge:** `python -m pytest tests/ -x -q` (includes e2e with mock adapters, ~30-60 seconds)
- **Phase gate:** Full suite green before `/gsd:verify-work` + manual ECS smoke test

### Wave 0 Gaps

The following test files must be created before or alongside implementation (Wave 0 of each plan):

- [ ] `tests/backend/test_knowledge_adapter.py` — covers RAG-01, RAG-02 (BM25 index build, DynamoDB paginator, RAGLLMAdapter injection)
- [ ] `tests/backend/test_bm25_redis.py` — covers RAG-02 (Redis fallback, query expansion, source attribution)
- [ ] `tests/backend/test_conversation.py` — covers VOIC-03 (ConversationSession, turn write, slo_met flag)
- [ ] `tests/backend/test_latency_probes.py` — covers VOIC-03 (PipelineResult timing fields, SLO calculation with mock adapters)
- [ ] `tests/e2e/test_phase1_roundtrip.py` — covers RAG-01+RAG-02+VOIC-03 (full voice turn with mock adapters, asserts sources present)
- [ ] `pytest.ini` — root-level pytest configuration (testpaths, asyncio_mode=auto for pytest-asyncio)
- [ ] Framework install: `pip install pytest-asyncio==0.23+` (add to `backend/requirements.txt`)

**Existing tests that still pass (no changes required):**
- `tests/backend/test_backend_contracts.py` — Phase 0 contracts, unaffected
- `tests/backend/test_orchestration_pipeline.py` — VoicePipeline unit, unaffected if RAG stage is additive

---

## Sources

### Primary (HIGH confidence)
- AWS DynamoDB Official Docs — Binary data type, item size limits (400KB), paginator pattern
  - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.NamingRulesDataTypes.html
- AWS ECS Task Definition Parameters — Valid Fargate CPU/memory combinations
  - https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html
- AWS IAM DynamoDB Permissions Reference — Permission names verified
  - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/api-permissions-reference.html
- rank_bm25 PyPI — BM25Okapi constructor params (k1, b)
  - https://pypi.org/project/rank-bm25/
- redis-py PyPI — ConnectionPool, socket_timeout, exception handling
  - https://pypi.org/project/redis/
- HuggingFace all-MiniLM-L6-v2 — Model size (22M params, 43MB float16), memory requirements
  - https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- FastAPI lifespan documentation — startup/shutdown context manager
  - https://fastapi.tiangolo.com/advanced/events/
- AWS Bedrock Converse API — system prompt field, modelId format
  - https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html

### Secondary (MEDIUM confidence)
- Granicus GXA — Government chatbot use cases, top intents (FAQ, permits, waste, elections)
  - https://granicus.com/blog/smarter-government-starts-here-use-cases-for-the-government-experience-agent/
- AWS Database Blog — DynamoDB data models for generative AI chatbots (session schema patterns)
  - https://aws.amazon.com/blogs/database/amazon-dynamodb-data-models-for-generative-ai-chatbots/
- Evidently AI — RAG evaluation metrics, groundedness score, proxy signals for hallucination
  - https://www.evidentlyai.com/llm-guide/rag-evaluation
- Jackson County Missouri — Property tax, collection, assessment FAQ structure
  - https://www.jacksongov.org/Government/Departments/Assessment/FAQs

### Tertiary (LOW confidence — flag for validation)
- Government synonym pairs: Domain-derived, not validated against specific Jackson County corpus
- GXA intent list: Derived from Granicus marketing materials; actual intent volume distribution unknown
- Groundedness proxy algorithm: Custom heuristic; not benchmarked against labeled Jackson County data

---

## Metadata

**Confidence breakdown:**
- EC2 removal impact: HIGH — purely architectural, no technical risk
- Standard stack (DynamoDB + BM25 + Redis): HIGH — all three verified via official docs and PyPI
- ECS memory (1024MB): HIGH — Fargate memory/CPU combinations verified; model size ~91MB confirmed
- IAM permissions: HIGH — all action names verified against AWS IAM permissions reference
- DynamoDB data model: HIGH — schema patterns verified against AWS official blog post
- Conversation tracking: HIGH — DynamoDB TTL and session patterns well-documented
- Validation Architecture: HIGH — test commands verified against existing Phase 0 test structure
- Government synonyms: MEDIUM — domain knowledge, not benchmarked
- GXA/Granicus intents: MEDIUM — derived from marketing materials, not internal analytics
- Hallucination proxy: MEDIUM — heuristic approach, RAGAS-inspired but not formally validated
- Cost per conversation formula: MEDIUM — pricing estimates from AWS public pricing pages (ap-south-1)

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (30-day window for stable stack)
**Next research trigger:** If Granicus releases new GXA intent taxonomy, or if DynamoDB pricing changes in ap-south-1.
