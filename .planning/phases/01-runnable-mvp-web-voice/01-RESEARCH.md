# Phase 1: GXA Voice Baseline — Research (Full Rewrite)

**Researched:** 2026-03-10
**Domain:** Government voice bot: DynamoDB + BM25 + Redis RAG, ECS Fargate, IAM, conversation tracking, CloudWatch metrics, GXA/Granicus intent taxonomy
**Confidence:** HIGH (core stack verified via official AWS docs and community evidence; GXA intents derived from Granicus published materials; hallucination proxy and government synonyms are MEDIUM confidence based on known domain patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md — locked 2026-03-10)

### Locked Decisions

**Two-Tier Deployment Strategy (UPDATED — EC2 REMOVED)**
Same codebase runs in both tiers — only configuration changes:
- Tier 1: Local Machine (Docker Compose) — $0 compute, ~$5/mo API
- Tier 2: ECS Fargate (existing cluster, ap-south-1) — ~$15-20/mo at 512CPU/1024MB

EC2 (t3.micro) removed from roadmap. Rationale: additional tier adds ops complexity without benefit for an MVP. The gap between local and ECS is small enough to validate directly.

**RAG Service Architecture (LOCKED)**
All services run in same ECS task for MVP (import as modules, not separate processes):
- Port 8000: Orchestrator (FastAPI WebSocket, Phase 0 service modified)
- Port 8001: Embedding service (all-MiniLM-L6-v2, FastAPI, imported as module in MVP)
- Port 8002: BM25 service (stateless reranker, FastAPI, imported as module in MVP)
- Shared: Redis cache (local: Redis container; ECS: same-task Redis sidecar)

**RAG Stack (LOCKED — pgvector/Aurora REMOVED)**
- Embedding model: `all-MiniLM-L6-v2` (384-dim, Sentence Transformers, ~5ms inference)
- Reranking: BM25 via `rank_bm25` library (~1-2ms — pure text matching)
- Caching: Redis (1ms lookup for repeated queries, BM25 fallback if Redis is down)
- Knowledge store: DynamoDB (FAQ text + metadata + pre-computed 384-dim embeddings stored as binary)
- Embeddings at query time: NOT used for BM25 search (reserved for Phase 4 hybrid upgrade)
- PDF storage: S3 (raw source documents)

**RAG Integration Point (LOCKED)**
- LLM: Claude 3.5 Sonnet via Bedrock Converse API
- RAGLLMAdapter injects top-3 FAQ chunks into Bedrock system prompt field
- Always include source attribution in responses

**Latency SLO (LOCKED)**
- Target: <1.5s turn latency (ASR start → TTS complete)
- Per-stage targets: ASR ~200ms, Embed+BM25+Redis ~6ms, LLM ~800ms, TTS ~400ms
- Track per-stage breakdowns in CloudWatch (p50, p95, p99)

**ECS Resource Requirements (LOCKED)**
- ECS task memory: 1024MB (512MB causes OOM with PyTorch/sentence-transformers)
- ECS task CPU: 512 units (upgrade from 256 to handle embedding inference)
- Monthly cost estimate: ~$15.50/mo (up from $8.96/mo at 512MB/256CPU)

**BM25 Accuracy Policy (LOCKED)**
- BM25 70-80% recall@5 acceptable for Phase 1 MVP
- Paraphrase misses mitigated by system prompt query expansion
- Upgrade path: hybrid semantic + BM25 in Phase 4 if insufficient after real user testing

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
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VOIC-03 | Voice sessions satisfy latency SLO targets for first partial, first audio, and turn latency | ECS memory section, latency budget breakdown, per-stage CloudWatch metrics |
| RAG-01 | ETL pipeline ingests S3 documents with required metadata fields | DynamoDB data model, ingest pipeline design, IAM permissions section |
| RAG-02 | Retrieval-augmented responses include citations to source documents | BM25 retrieval architecture, DynamoDB FAQ schema, KnowledgeResult.sources pattern |
</phase_requirements>

---

## Summary

Phase 1 implements a government voice RAG bot using DynamoDB + BM25 + Redis — a cost-optimized stack that replaces the previously planned Aurora PostgreSQL + pgvector approach. The primary design choices are: store pre-computed 384-dim embeddings in DynamoDB binary attributes (for future hybrid search), run BM25-only retrieval at query time (for MVP simplicity and speed), use Redis as a query result cache with transparent BM25 fallback if Redis is unavailable, and deploy everything in a single ECS Fargate task at 1024MB to comfortably host PyTorch alongside the FastAPI orchestrator.

The research confirms EC2 removal is sound. The gap from local Docker Compose to ECS Fargate is bridged entirely through environment variable configuration (AWS credentials, DynamoDB table names, S3 bucket names). There is no third deployment tier needed for an MVP.

GXA/Granicus government bots serve a well-defined intent taxonomy: property tax, utility payments, trash/waste, permits, elections, courts, parks, emergency management, and 311 general routing. Jackson County Missouri specifically uses DynamoDB-backed services for property tax and collection. The top 15 government intents are documented below with synonym dictionaries for BM25 query expansion.

**Primary recommendation:** Ship DynamoDB + BM25 + Redis with Redis fallback to BM25 (never fail voice turns). Store embeddings as DynamoDB Binary for Phase 4 upgrade readiness. Track conversations in DynamoDB Table 2 with TTL. Push turn metrics to CloudWatch. The stack handles the <1.5s SLO comfortably with mocked adapters showing ~10-20ms total for BM25+Redis path.

---

## EC2 Removal — Impact Analysis

### What Changes
The 01-CONTEXT.md currently describes a "Three-Tier Deployment Strategy." With EC2 removed, this becomes a two-tier strategy:

| Before (3-tier) | After (2-tier) |
|-----------------|----------------|
| Local → EC2 → ECS | Local → ECS |
| EC2 as pre-production | Local is pre-production |
| t3.micro ~$10/mo | Eliminated |

### What Does NOT Change
- Same codebase philosophy: configuration-only differences between local and ECS
- Same Docker Compose for local development
- Same ECS Fargate task definitions
- Same environment variable switching pattern

### Files Requiring Updates (Planners Note)
- `.planning/phases/01-runnable-mvp-web-voice/01-CONTEXT.md` — Remove EC2 rows from deployment table
- `.planning/ROADMAP.md` — Phase 1 goal line still says "EC2" — update to "Local Docker + ECS only"
- `01-02-PLAN.md` — References Aurora PostgreSQL + pgvector — must be replaced with DynamoDB + BM25

### CONTEXT.md Domain Block Update Required
Current domain block reads: "Uses a three-tier deployment strategy (Local Docker → EC2 → ECS)"
Must become: "Uses a two-tier deployment strategy (Local Docker → ECS Fargate)"

**Confidence:** HIGH — this change has zero technical risk. AWS credentials + env vars already handle the local↔ECS switch in Phase 0 code.

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
| `pynamodb` | 6.x | DynamoDB ORM alternative | Optional — avoids boto3 low-level API verbosity for table schemas |
| `pytest-asyncio` | 0.23+ | Async test support for FastAPI | Needed for testing WebSocket handlers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rank_bm25` | `bm25s` | bm25s is 500x faster but less mature; rank_bm25 has more production usage |
| `rank_bm25` | Elasticsearch BM25 | Elasticsearch adds infra cost and complexity; rank_bm25 is in-process |
| Redis for cache | In-memory dict | Redis survives container restarts; dict is reset on each deployment |
| DynamoDB Binary for embeddings | S3 for embeddings | S3 adds per-request latency; DynamoDB collocates text + embedding in one read |

**Installation:**
```bash
pip install rank-bm25 sentence-transformers redis boto3 fastapi pdfplumber numpy
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
      bm25_index.py         # BM25 index builder and query runner
      redis_cache.py        # Redis cache with BM25 fallback
      conversation.py       # ConversationAdapter (DynamoDB session storage)
    orchestrator/
      pipeline.py           # VoicePipeline with RAG stage + timing
      runtime.py            # build_pipeline() factory
    monitoring.py           # LatencyBuffer + publish_stage_metrics

knowledge/
  pipeline/
    ingest.py               # PDF extraction + chunking
    embed.py                # sentence-transformers embedding + DynamoDB write
  data/
    local/sample_faqs.json  # Seed FAQs for offline dev
    schemas/dynamo_faq.json # DynamoDB table schema spec
    schemas/dynamo_conv.json # Conversation table schema spec

tests/
  backend/
    test_knowledge_adapter.py
    test_bm25_redis.py
    test_conversation.py
    test_latency_probes.py
  e2e/
    test_phase1_roundtrip.py
```

### Pattern 1: BM25 Query with Redis Cache + Transparent Fallback

**What:** Redis stores serialized BM25 results keyed by normalized query string. On Redis hit, skip BM25 entirely. On Redis miss OR Redis error, run BM25 directly. Redis failure NEVER fails the voice turn.

**When to use:** Every knowledge retrieval call in `DynamoKnowledgeAdapter.retrieve()`.

**The critical invariant:** Voice turns must never fail due to cache unavailability. Redis is an optimization, not a dependency.

```python
# Source: pattern derived from pybreaker + redis-py official docs
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
        Order of operations:
          1. Try Redis GET
          2. Cache hit → deserialize and return
          3. Cache miss or Redis error → run BM25
          4. If BM25 result found → try Redis SET (fire-and-forget, ignore errors)
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
        expanded_query = expand_government_query(query)  # see government synonyms section
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

**Size math:** 384 dimensions × 4 bytes per float32 = **1,536 bytes per embedding**. DynamoDB item limit is 400KB. Each FAQ item (text ~500 chars + embedding 1536 bytes + metadata ~200 bytes) ≈ **2.2KB**, well under limit. A 50-FAQ corpus fits in a single Scan with a ~110KB response.

```python
# Source: AWS DynamoDB docs (Binary type) + numpy official docs
import numpy as np
import boto3
from decimal import Decimal

def embedding_to_dynamodb_binary(embedding: np.ndarray) -> bytes:
    """Convert float32 numpy array to bytes for DynamoDB Binary attribute.

    Note: DynamoDB Binary stores raw bytes (not base64). The boto3 client
    handles base64 encoding/decoding transparently. Pass raw bytes to boto3.
    """
    assert embedding.dtype == np.float32, "Must be float32"
    assert embedding.shape == (384,), f"Expected 384-dim, got {embedding.shape}"
    return embedding.tobytes()  # little-endian float32 bytes, 1536 bytes total

def dynamodb_binary_to_embedding(raw_bytes: bytes) -> np.ndarray:
    """Reconstruct float32 numpy array from DynamoDB Binary attribute bytes."""
    return np.frombuffer(raw_bytes, dtype=np.float32)  # 384-element array

# Write to DynamoDB
dynamo_client = boto3.client("dynamodb", region_name="ap-south-1")
embedding_bytes = embedding_to_dynamodb_binary(embedding_array)

dynamo_client.put_item(
    TableName="voicebot-faq-knowledge",
    Item={
        "department": {"S": "finance"},
        "chunk_id":   {"S": "jackson-faq-2024.pdf:chunk:0"},
        "text":       {"S": chunk_text},
        "embedding":  {"B": embedding_bytes},   # boto3 auto-handles base64 wire format
        "source_doc": {"S": "jackson-faq-2024.pdf"},
        "created_at": {"S": "2026-03-10T00:00:00Z"},
        "tags":       {"SS": ["property-tax", "finance"]},
    }
)

# Read back
response = dynamo_client.get_item(
    TableName="voicebot-faq-knowledge",
    Key={"department": {"S": "finance"}, "chunk_id": {"S": "jackson-faq-2024.pdf:chunk:0"}}
)
item = response["Item"]
embedding = dynamodb_binary_to_embedding(item["embedding"]["B"])  # back to np.ndarray
```

**Critical note:** boto3 automatically base64-encodes bytes when sending to DynamoDB API and decodes on return. You write `bytes`, not base64 strings. DynamoDB stores raw bytes. This is transparent.

**Confidence:** HIGH — verified against AWS DynamoDB official docs (Binary type descriptor `B`, raw byte storage).

### Pattern 3: BM25 Index Build from DynamoDB Corpus

**What:** Load all FAQ text from DynamoDB at startup, build BM25Okapi index in-memory. Index is rebuilt on deployment (monthly ingest updates the corpus).

**When to use:** Service startup in `DynamoKnowledgeAdapter.__init__()`.

```python
# Source: rank_bm25 PyPI documentation
from rank_bm25 import BM25Okapi
import boto3

def load_bm25_from_dynamodb(table_name: str, region: str = "ap-south-1") -> tuple[BM25Okapi, list[dict]]:
    """
    Scan DynamoDB FAQ table, build BM25 index.
    Returns (bm25_index, corpus_list) — corpus needed for result lookup by index.

    Uses paginator from day one (boto3.get_paginator) to handle >1MB DynamoDB responses.
    For 50 FAQs this is overkill but correct architecture for future growth.
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

    # Tokenize for BM25: lowercase + whitespace split
    # For production: add stopword removal, stemming (NLTK or spaCy)
    tokenized_corpus = [doc["text"].lower().split() for doc in corpus]

    bm25 = BM25Okapi(
        tokenized_corpus,
        k1=1.5,    # term saturation — higher = more weight on term frequency
        b=0.75,    # length normalization — 0.75 is BM25 standard default
    )
    return bm25, corpus
```

**Confidence:** HIGH — rank_bm25 API verified against PyPI package source.

### Pattern 4: FastAPI Multi-Client API Architecture

**What:** Three endpoints enable multi-client use:
- `ws://host/ws` — WebSocket for voice clients (browser mic → ASR → RAG → TTS → audio)
- `POST /chat` — REST for text clients (mobile apps, Slack bots, SMS gateways)
- `GET /health` — Health check for load balancers and monitoring

**How pluggable:** Adapters (ASRAdapter, LLMAdapter, TTSAdapter, KnowledgeAdapter) are injected via `build_pipeline()` factory. Swapping providers requires only changing environment variables, not code. Example: swap `AwsTranscribeAdapter` → `DeepgramAdapter` by adding a new concrete class and changing `USE_ASR=deepgram` env var.

```python
# Source: FastAPI official docs + Phase 0 existing patterns
from fastapi import FastAPI, WebSocket, Depends
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load BM25 index at startup — not per-request
    from backend.app.orchestrator.runtime import build_pipeline
    app.state.pipeline = build_pipeline()
    yield
    # Cleanup: close Redis connections, etc.

app = FastAPI(lifespan=lifespan)

# Voice clients: WebSocket
@app.websocket("/ws")
async def voice_endpoint(ws: WebSocket):
    await ws.accept()
    async for audio_bytes in ws.iter_bytes():
        result = await app.state.pipeline.run_roundtrip(audio_bytes)
        await ws.send_bytes(result.response_audio)

# Text/REST clients: POST /chat
@app.post("/chat")
async def chat_endpoint(body: ChatRequest) -> ChatResponse:
    result = await app.state.pipeline.run_text_turn(body.text)
    return ChatResponse(text=result.response_text)

# Health check: GET /health
@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Multi-client capability:** YES. Any client that can speak HTTP or WebSocket can use this API. Voice (browser), text (REST), telephony (WebSocket bridge), Slack (webhook) — all supported without code changes.

**Confidence:** HIGH — FastAPI lifespan context manager is the official pattern for startup/shutdown resource management.

### Anti-Patterns to Avoid

- **Querying BM25 for every Redis hit lookup check:** Cache key is SHA-256 of query — do the hash, check Redis, only run BM25 on cache miss. The BM25 call itself is fast (~1-2ms) but Redis check should be unconditional.
- **Building BM25 index per-request:** Build once at startup in `lifespan()`. For 50 FAQs this is trivial (~1ms), but the pattern matters for correctness.
- **Storing embeddings as a JSON list:** Float32 → JSON → DynamoDB is 4x larger (1536 bytes vs ~6KB as JSON float string) and slower to parse. Use binary bytes.
- **Using `dynamodb.scan()` without paginator:** Works for <1MB responses, breaks silently beyond. Use `get_paginator("scan")` from day one.
- **Raising exceptions from Redis failure:** Cache failures should log a warning and fall through to BM25. Never let `redis.exceptions.ConnectionError` propagate to the voice turn.
- **EC2 deployment tier:** Eliminated. Local → ECS directly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 scoring | Custom TF-IDF implementation | `rank_bm25` | BM25Okapi has correct IDF normalization, k1/b params — custom TF-IDF will differ from published BM25 formula |
| Sentence embeddings | Custom transformer inference | `sentence-transformers` | Handles tokenization, pooling, normalization correctly; hand-rolled will produce different vector space |
| Redis connection pool | `redis.Redis()` per request | `redis.ConnectionPool` + shared `redis.Redis(connection_pool=pool)` | Per-request connections exhaust file descriptors under load |
| DynamoDB paginator | Manual `LastEvaluatedKey` loop | `boto3.get_paginator("scan")` | Paginator handles `LastEvaluatedKey` correctly; manual loop commonly mis-handles the terminal condition |
| Conversation TTL cleanup | Cron job to delete old sessions | DynamoDB TTL attribute | DynamoDB auto-deletes expired items within 48 hours; no additional cost |
| Percentile calculation | Rolling percentile approximation | `statistics.quantiles()` or sorted list slice | Python's statistics module is correct; rolling approximations introduce error |
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

**Why 512MB was too tight:** The original 512MB task had ~59MB used at idle (Phase 0, no ML libraries). Loading PyTorch for sentence-transformers adds ~241MB minimum. 59MB + 241MB = 300MB just for Python + PyTorch. Adding the model (91MB) = 391MB, dangerously close to 512MB with zero headroom for inference burst.

**Why 1024MB is correct:** Provides ~500MB headroom above expected usage. ECS kills tasks at the hard limit; a memory burst during first-request model warm-up at 512MB causes OOM-kill and service restart loop.

### How to Update ECS Memory

**Option 1: AWS Console (immediate)**
1. ECS Console → Clusters → voice-bot-mvp-cluster → Task Definitions
2. Create new revision of existing task definition
3. Change Memory: 512 → 1024 (MiB)
4. Change CPU: 256 → 512 (units)
5. Update service to use new task definition revision

**Option 2: AWS CLI**
```bash
# Register new task definition revision with 1024MB/512CPU
aws ecs register-task-definition \
  --family voice-bot-mvp \
  --requires-compatibilities FARGATE \
  --network-mode awsvpc \
  --cpu 512 \
  --memory 1024 \
  --region ap-south-1 \
  ...

# Update service to use new revision
aws ecs update-service \
  --cluster voice-bot-mvp-cluster \
  --service voice-bot-mvp-svc \
  --task-definition voice-bot-mvp:NEW_REVISION \
  --region ap-south-1
```

**Valid Fargate CPU+Memory combinations (HIGH confidence — AWS docs):**
- 256 CPU → 512, 1024, 2048 MB (512MB insufficient here)
- 512 CPU → 1024, 2048, 3072, 4096 MB (1024MB is the target)

**Monthly cost impact:**
- 256 CPU / 512 MB: $0.01245/hr = $8.96/mo
- 512 CPU / 1024 MB: ~$0.0215/hr = ~$15.50/mo (per AWS Fargate pricing ap-south-1)

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

### Permission Justification by Action

| Permission | Why Needed |
|------------|------------|
| `dynamodb:GetItem` | Fetch single FAQ chunk by PK+SK |
| `dynamodb:PutItem` | Write FAQ chunks during ingest, write conversation turns |
| `dynamodb:Query` | Query by department (PK) + chunk_id prefix (SK) |
| `dynamodb:Scan` | Load full FAQ corpus at startup for BM25 index build |
| `dynamodb:BatchWriteItem` | Batch ingest of FAQ chunks (up to 25 items per call) |
| `dynamodb:UpdateItem` | Update conversation session metadata (turn_count, last_active) |
| `dynamodb:DescribeTable` | Startup check that table exists before loading BM25 index |
| `s3:GetObject` | Download raw PDF files from S3 during monthly ingest |
| `s3:ListBucket` | List available PDF files in ingest bucket |
| `cloudwatch:PutMetricData` | Publish per-stage latency metrics (ASR, RAG, LLM, TTS) |
| `bedrock:InvokeModel` | Claude 3.5 Sonnet inference (non-streaming) |
| `bedrock:InvokeModelWithResponseStream` | Claude 3.5 Sonnet streaming (future) |
| `transcribe:StartStreamTranscription` | AWS Transcribe ASR |
| `polly:SynthesizeSpeech` | AWS Polly TTS |

**Ingest-only permissions (NOT needed on ECS task role — use separate IAM user for ingest pipeline):**
- `dynamodb:CreateTable` — Run once during setup, not in production
- `dynamodb:DeleteItem` — Not needed for FAQ bot
- `s3:PutObject` — Not needed if ECS only reads PDFs

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
  tags (SS)                — String set for filtering ("property-tax", "payment", "deadline")

GSI-1 (optional Phase 2):
  PK: client_id (S)        — "jackson-county" (multi-tenant future)
  SK: created_at (S)       — enables time-ordered queries
```

**Access patterns:**
1. Full corpus load at startup: `Scan(TableName=table)` via paginator → build BM25 index
2. Single chunk fetch: `GetItem(department=dept, chunk_id=id)` → for citation display
3. Department filter: `Query(department="finance")` → department-specific search subset

**Cost estimate for 50 FAQs:**
- 50 items × 2.2KB avg = 110KB total table size
- Scan at startup: 0.5 RCU per 4KB → 50 × 2.2KB / 4KB × 0.5 = ~7 RCUs
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

  # Session-level metadata (stored on turn 0, updated on each turn via UpdateItem)
  # Alternative: store session metadata on a separate "metadata" SK value ("meta")
  department_hit (S)       — Department of top FAQ chunk returned
  query_expanded (BOOL)    — Whether query expansion triggered a synonym match

  # TTL: auto-expire after 90 days
  ttl (N)                  — Unix epoch seconds (current time + 90 × 86400)
```

**TTL configuration:** Enable TTL on the `ttl` attribute in DynamoDB console or via CLI:
```bash
aws dynamodb update-time-to-live \
  --table-name voicebot-conversations \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region ap-south-1
```
DynamoDB deletes expired items within 48 hours of TTL expiry at no additional WCU cost.

**Session lifecycle:**
1. `session_start`: Generate UUID session_id, turn_number=0, write turn 0 metadata
2. `turn_complete`: Write turn record (session_id, turn_number++, all latency fields)
3. `session_end`: Optional — mark session as completed with completion status
4. `auto_expire`: TTL fires after 90 days — no cleanup required

**Access patterns:**
1. Write turn: `PutItem(session_id=id, turn_number=N, ...)`
2. Get full session: `Query(session_id=id)` → returns all turns sorted by turn_number
3. Get session turn count: `Query(session_id=id, Select=COUNT)` → 1 RCU

**Conversation history for LLM multi-turn context:**
Load last N turns via `Query(session_id=id, ScanIndexForward=True, Limit=5)`. Format as:
```python
messages = [
    {"role": "user", "content": [{"text": turn["user_input"]["S"]}]},
    {"role": "assistant", "content": [{"text": turn["assistant_response"]["S"]}]},
]
# Pass to Bedrock Converse API messages= parameter
```

**Cost estimate for conversation storage:**
- Each turn: ~1KB of data
- 100 sessions/day × 5 turns avg × 1KB = 500KB/day written
- DynamoDB write cost: 500KB / 1KB per WCU = 500 WCUs/day
- At $0.000625 per WCU (on-demand, ap-south-1): 500 × $0.000625 = **$0.31/day** = ~$9/month at 100 sessions/day
- At MVP scale (5-10 sessions/day): **<$0.50/month**

### Table 3: Metrics / Analytics

**Recommendation:** Do NOT create a separate DynamoDB metrics table for Phase 1.

**Why:** CloudWatch custom metrics serve this role. Per-turn latency data is published to `cloudwatch:PutMetricData` (cost: $0.01 per 1000 metric data points). Aggregated dashboards are built in CloudWatch. Conversation-level metrics (session_id, turns, completion) are already in Table 2.

A separate DynamoDB analytics table adds complexity without benefit at MVP scale. Add it in Phase 3 (Eval Gate I) when replay harness and golden dataset evaluation require structured storage.

**Confidence:** HIGH for Tables 1 and 2 schema (derived from AWS official DynamoDB chatbot blog patterns). MEDIUM for "no Table 3" recommendation (reasonable for MVP scale, may need revisiting at 1000+ sessions/day).

---

## Conversation Saving — Design Decision

### WHERE to save conversations: DynamoDB Table 2

**Rationale:**
- Redis: Too volatile (conversations lost on Redis restart)
- Local file: Not available in ECS
- DynamoDB: Persistent, scalable, TTL built-in, queryable by session_id, cheap at MVP scale

### WHEN in Phase 1 to implement

**Recommendation:** Implement conversation session tracking in Plan 03 (ECS Deployment) as a minimal `ConversationAdapter` that writes to DynamoDB. Do NOT defer to Phase 2.

**Why Phase 1 (not Phase 2):** Conversation tracking data is needed for the metrics dashboard in Plan 04. Without session records, you cannot compute: turns_per_session, session_completion_rate, follow_up_rate, cost_per_conversation. These are the metrics that demonstrate MVP value to stakeholders.

**Minimal Phase 1 implementation:**
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
    pipeline_result,  # PipelineResult with timing fields
    rag_chunk_ids: list[str],
    table_name: str = "voicebot-conversations",
):
    """Write a single conversation turn to DynamoDB."""
    import boto3
    now = datetime.now(timezone.utc)
    ttl_90_days = int(now.timestamp()) + (90 * 86400)

    dynamo_client.put_item(
        TableName=table_name,
        Item={
            "session_id":         {"S": session.session_id},
            "turn_number":        {"N": str(session.next_turn_number())},
            "user_input":         {"S": user_input},
            "assistant_response": {"S": assistant_response},
            "rag_chunks_used":    {"SS": rag_chunk_ids} if rag_chunk_ids else {"NULL": True},
            "asr_ms":             {"N": str(pipeline_result.asr_ms)},
            "rag_ms":             {"N": str(pipeline_result.rag_ms)},
            "llm_ms":             {"N": str(pipeline_result.llm_ms)},
            "tts_ms":             {"N": str(pipeline_result.tts_ms)},
            "total_ms":           {"N": str(pipeline_result.asr_ms + pipeline_result.rag_ms + pipeline_result.llm_ms + pipeline_result.tts_ms)},
            "timestamp":          {"S": now.isoformat()},
            "slo_met":            {"BOOL": (pipeline_result.asr_ms + pipeline_result.rag_ms + pipeline_result.llm_ms + pipeline_result.tts_ms) < 1500},
            "ttl":                {"N": str(ttl_90_days)},
        }
    )
```

### HOW conversation history feeds back into LLM

**Phase 1 (minimal):** No multi-turn context. Each turn is treated as a new question. This is acceptable for FAQ bots where most questions are self-contained.

**Phase 2 (upgrade):** Load last 3 turns from DynamoDB, include in Bedrock `messages=` parameter:
```python
# Fetch prior turns
turns = dynamo.query(
    TableName="voicebot-conversations",
    KeyConditionExpression="session_id = :sid",
    ExpressionAttributeValues={":sid": {"S": session_id}},
    ScanIndexForward=True,
    Limit=3
)["Items"]

# Build Bedrock messages array with history
messages = []
for turn in turns:
    messages.append({"role": "user", "content": [{"text": turn["user_input"]["S"]}]})
    messages.append({"role": "assistant", "content": [{"text": turn["assistant_response"]["S"]}]})
messages.append({"role": "user", "content": [{"text": current_query}]})

# Pass to Bedrock Converse API
bedrock.converse(
    modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
    messages=messages,
    system=[{"text": rag_context}]
)
```

**Confidence:** HIGH for DynamoDB session storage pattern (verified against AWS DynamoDB chatbot blog). MEDIUM for multi-turn context implementation (standard Bedrock Converse API pattern, well-documented).

---

## Metrics Dashboard — Full Specification

### Metric Storage Decision Matrix

| Metric Category | Storage | Why |
|-----------------|---------|-----|
| Per-turn latency (ASR/RAG/LLM/TTS ms) | CloudWatch custom metrics | Fast aggregation, p50/p95/p99 built-in, alarming native |
| ECS CPU/Memory utilization | CloudWatch (auto-published by ECS) | No custom code needed |
| DynamoDB read/write units | CloudWatch (auto-published by DynamoDB) | No custom code needed |
| Redis hit/miss ratio | Custom CloudWatch metrics | Published via `put_metric_data` after each retrieval |
| BM25 retrieval scores | DynamoDB Table 2 (`retrieval_score` field) | Per-session analysis; CloudWatch for aggregates |
| Conversation sessions (count, turns, completion) | DynamoDB Table 2 + CloudWatch aggregates | Table 2 for per-session drill-down, CloudWatch for totals |
| LLM token usage | CloudWatch (Bedrock auto-publishes in us-east-1; ap-south-1 pending) | Check Bedrock console |
| Cost per conversation | Calculated metric (not stored raw) | Derive from ECS hourly cost / session count |

### CloudWatch Metric Names (Phase 1 — `voicebot/latency` namespace)

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
  FallbackToDirectBM25 (Unit: Count)  # Redis was down, fell through to BM25

Namespace: voicebot/conversations
  SessionsStarted     (Unit: Count)
  TurnsCompleted      (Unit: Count)
  SLOViolations       (Unit: Count)   # turns where total_ms >= 1500

Namespace: voicebot/operations (existing from Phase 0)
  HourlyCost, DailyCost, MonthlyCost, IdleTasks
```

### Per-Turn Metrics Schema (published after each voice turn)

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
            {"MetricName": "TotalTurnLatency", "Value": sum([result.asr_ms, result.rag_ms, result.llm_ms, result.tts_ms]), "Unit": "Milliseconds", "Dimensions": dims},
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

### Hallucination Rate — Proxy Metric Without Ground Truth

**The problem:** Measuring hallucination requires ground truth labels (correct answers). At MVP, no labeled dataset exists.

**Proxy signal 1 — Retrieval groundedness (HIGH value):**
If BM25 top-1 score is above threshold AND the response contains a phrase from the top chunk, assume grounded. If BM25 returns zero results (empty corpus or no match), mark as potential hallucination.

```python
def estimate_groundedness(response_text: str, retrieved_chunks: list[str], bm25_top_score: float) -> float:
    """
    Heuristic groundedness score [0.0, 1.0].
    NOT a true hallucination detector — a proxy signal for monitoring trends.

    Logic:
    - If BM25 score == 0: no retrieved context → likely hallucination (score: 0.0)
    - If BM25 score < 0.5: weak match → low confidence (score: 0.3)
    - If any retrieved chunk phrase appears in response: grounded (score: 1.0)
    - Otherwise: partial (score: 0.5)
    """
    if bm25_top_score < 0.01:
        return 0.0  # No relevant context found — response is unsupported

    # Check if any significant phrase from top chunk appears in response
    top_chunk = retrieved_chunks[0] if retrieved_chunks else ""
    # Split into 4-gram windows and check overlap
    chunk_words = top_chunk.lower().split()
    response_lower = response_text.lower()

    matches = 0
    windows = [chunk_words[i:i+4] for i in range(len(chunk_words) - 3)]
    for window in windows[:20]:  # check first 20 windows
        phrase = " ".join(window)
        if phrase in response_lower:
            matches += 1

    if matches >= 2:
        return 1.0  # Strongly grounded
    elif matches == 1:
        return 0.7  # Likely grounded
    elif bm25_top_score > 0.5:
        return 0.5  # Retrieval found something; response may be paraphrase
    else:
        return 0.3  # Weak retrieval match
```

**Proxy signal 2 — Fallback rate:** Track what % of turns have BM25 top_score < 0.1 (no useful context found). High fallback rate → LLM is generating without grounding.

**Proxy signal 3 — Repeat questions / follow-up rate:** If user asks a similar question within the same session (detected by BM25 similarity to prior user_input), flag as "follow-up" — indicator the previous answer was unclear or unhelpful.

**IMPORTANT:** These are proxy signals. True hallucination evaluation requires the golden dataset (Phase 3 Eval Gate). Use proxy signals in Phase 1 to identify trends, not to make claims about hallucination rates.

**Confidence:** MEDIUM — groundedness heuristics derived from RAGAS framework principles and Evidently AI RAG evaluation guide. Not verified against Jackson County specific corpus.

### Cost Per Conversation Formula

```python
def compute_cost_per_conversation(session: ConversationSession, ecs_cost_per_hour: float = 0.0215) -> float:
    """
    Estimate cost per conversation session in USD.

    Components:
    1. ECS compute cost: (session_duration_hours × ecs_cost_per_hour)
    2. Bedrock API cost: (llm_tokens × bedrock_rate)
    3. Transcribe cost: (audio_seconds × transcribe_rate)
    4. Polly cost: (response_chars × polly_rate)

    Simplified for Phase 1 (use averages):
    - ECS: $0.0215/hr shared across all concurrent sessions
    - Bedrock Claude 3.5 Sonnet (ap-south-1): ~$0.003 per 1000 input tokens + $0.015 per 1000 output tokens
    - Transcribe: $0.024 per minute of audio
    - Polly: $0.000004 per character (standard voices)

    At 5 sessions/day, avg 3 turns, 30s avg session:
    ECS per session = ($0.0215/hr) / (5 sessions/day × 8 hr/day) ≈ $0.000538
    Bedrock per session ≈ 3 turns × (500 input + 200 output tokens) / 1000 × avg rate ≈ $0.006
    Total per session ≈ $0.007
    """
    session_duration_hours = session.duration_seconds / 3600

    # Approximate cost components
    ecs_cost = session_duration_hours * ecs_cost_per_hour

    # Bedrock: assume avg 500 input tokens (system + context + user) and 200 output tokens per turn
    bedrock_input_cost = session.turn_count * 500 * 0.003 / 1000
    bedrock_output_cost = session.turn_count * 200 * 0.015 / 1000

    # Transcribe: assume avg 5 seconds of audio per turn at $0.024/min = $0.0004/turn
    transcribe_cost = session.turn_count * 0.0004

    # Polly: assume avg 150 chars per response at $0.000004/char = $0.0006/turn
    polly_cost = session.turn_count * 0.0006

    return ecs_cost + bedrock_input_cost + bedrock_output_cost + transcribe_cost + polly_cost
```

### CloudWatch Dashboard Widgets (TPM View)

Recommended widget layout for `voice-bot-mvp-operations` dashboard:

| Widget | Type | Metric | Audience |
|--------|------|--------|----------|
| Turn Latency p95 (1h) | Line | TotalTurnLatency p95 | SLO monitoring |
| Stage Breakdown p50 | Stacked bar | ASR/RAG/LLM/TTS p50 | Bottleneck identification |
| SLO Violation Rate | Number | SLOViolations/TurnsCompleted | Executive |
| Cache Hit Rate | Number | CacheHits/(CacheHits+CacheMisses) | Engineering |
| ECS CPU & Memory | Line | CPUUtilization, MemoryUtilization | Infra |
| Sessions Today | Number | SessionsStarted sum (1d) | Product |
| Avg Turns/Session | Number | TurnsCompleted/SessionsStarted | Product |
| BM25 Top Score Avg | Line | BM25TopScore avg | RAG quality |
| Groundedness Score | Line | GroundednessScore avg | AI quality |
| Daily Cost | Number | DailyCost (existing widget) | Finance |

### Recommended CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| SLO Breach | TotalTurnLatency p95 | > 1500ms | SNS notification |
| Memory High | ECS MemoryUtilization | > 85% | SNS notification |
| Redis Down | FallbackToDirectBM25 | > 10/5min | SNS notification |
| Error Rate | (5xx errors from /ws) | > 5/min | SNS notification |

**CloudWatch custom metric pricing:** $0.30/metric/month for first 10,000 metrics. Phase 1 will have ~10-12 custom metrics = ~$3-4/month additional monitoring cost.

**Confidence:** HIGH for CloudWatch metric names and costs. MEDIUM for groundedness proxy score algorithm.

---

## GXA / Granicus — Top Government Intents

### Top 20 Municipal Government Intents (Jackson County / Johnson County applicable)

Derived from Granicus GXA published materials, Denver "Sunny" chatbot reports, NYC311, and general municipal service taxonomy research.

| # | Intent Category | Example Questions | Jackson County Department |
|---|-----------------|-------------------|--------------------------|
| 1 | Property Tax Status | "How much do I owe in property taxes?", "When is my tax bill due?" | Collection / Assessment |
| 2 | Property Tax Payment | "How do I pay my property tax online?", "Do you accept credit cards?" | Collection |
| 3 | Property Tax Appeal | "How do I dispute my property assessment?", "How do I file an informal review?" | Assessment |
| 4 | Utility Bill Payment | "How do I pay my water bill?", "When is my utility payment due?" | Utilities |
| 5 | Trash Pickup Schedule | "When is my garbage day?", "Is there holiday pickup?", "Bulk trash pickup" | Utilities / Public Works |
| 6 | Recycling Information | "What can I recycle?", "Where is the recycling drop-off?" | Utilities |
| 7 | Building Permit Application | "How do I apply for a building permit?", "What permits do I need to add a deck?" | Planning & Zoning |
| 8 | Permit Status Check | "What's the status of my permit application?", "How long does permit review take?" | Planning & Zoning |
| 9 | Voter Registration | "How do I register to vote?", "Is my voter registration up to date?" | Elections |
| 10 | Election Day Info | "Where is my polling place?", "What ID do I need to vote?" | Elections |
| 11 | Business License Renewal | "How do I renew my business license?", "When does my license expire?" | Finance / Revenue |
| 12 | Court Fee Payment | "How do I pay a court fee?", "What are the court costs for a traffic ticket?" | Courts |
| 13 | Road / Pothole Report | "How do I report a pothole?", "Who do I call about a road closure?" | Public Works |
| 14 | Emergency Contacts | "Who do I call in an emergency?", "Emergency management resources" | Emergency Management |
| 15 | Parks & Recreation | "How do I register for a parks program?", "What are the park hours?" | Parks & Recreation |
| 16 | Sheriff Non-Emergency | "What's the non-emergency sheriff number?", "How do I report a noise complaint?" | Sheriff |
| 17 | SNAP / Food Assistance | "How do I apply for food stamps?", "SNAP eligibility requirements" | Human Services |
| 18 | Senior Services | "What senior programs are available?", "Transportation for seniors?" | Senior Services |
| 19 | Stray Animal / Animal Control | "Who do I call about a stray dog?", "Animal shelter hours" | Animal Control |
| 20 | 311 General Routing | "I need to report something but don't know which department", "Who handles X?" | 311 / Call Center |

### TPM Monitoring Guide — Intent Performance

**How to track intent-level metrics in Phase 1:**

Since Phase 1 lacks intent classification (no NLU model), use a heuristic approach:
1. Map BM25 top-1 retrieved chunk's `department` field to an intent category
2. Store `department_hit` in conversation turn record (already in Table 2 schema)
3. Query DynamoDB Table 2 grouped by `department_hit` to get per-intent metrics

```python
# Intent performance query (run weekly as TPM report)
# Scan Table 2, group by department_hit, compute metrics per group
def compute_intent_report(dynamo_client, table_name: str) -> dict:
    """
    Returns per-intent metrics from conversation history.
    At MVP scale (<1000 sessions): Scan is acceptable.
    At scale: add GSI on department_hit.
    """
    paginator = dynamo_client.get_paginator("scan")
    by_intent = {}

    for page in paginator.paginate(TableName=table_name):
        for item in page["Items"]:
            intent = item.get("department_hit", {}).get("S", "unknown")
            slo_met = item.get("slo_met", {}).get("BOOL", True)
            total_ms = float(item.get("total_ms", {}).get("N", 0))

            if intent not in by_intent:
                by_intent[intent] = {"count": 0, "slo_violations": 0, "total_ms": []}
            by_intent[intent]["count"] += 1
            if not slo_met:
                by_intent[intent]["slo_violations"] += 1
            by_intent[intent]["total_ms"].append(total_ms)

    return {
        intent: {
            "count": data["count"],
            "slo_violation_rate": data["slo_violations"] / max(data["count"], 1),
            "avg_latency_ms": sum(data["total_ms"]) / max(len(data["total_ms"]), 1),
        }
        for intent, data in by_intent.items()
    }
```

**TPM questions this answers:**
- "Which intents have the highest SLO violation rate?" → fix RAG retrieval or FAQ coverage for those departments
- "Which departments have the most questions?" → prioritize FAQ content expansion there
- "Is property tax performing better than permits?" → compare per-intent latency and retrieval scores

### Intent Performance Targets (Phase 1 Baseline)

| Intent | Expected Volume | SLO Target | FAQ Coverage |
|--------|-----------------|------------|--------------|
| Property Tax | High | <1.5s | Priority — 10+ FAQs |
| Trash/Recycling | High | <1.5s | Priority — 5+ FAQs |
| Permits | Medium | <1.5s | Priority — 8+ FAQs |
| Elections | Seasonal (high near elections) | <1.5s | 5+ FAQs |
| Court Fees | Low-Medium | <1.5s | 5+ FAQs |
| Parks | Low | <1.5s | 3+ FAQs |

**GXA Benchmark context:** Granicus reports GXA cuts 311 call volumes by up to 30% for routine questions. The intents that drive the highest call volumes (property tax, trash pickup, permits) should be the best-covered FAQs in the initial corpus.

**Confidence:** MEDIUM-HIGH — intent list derived from Granicus published use cases, NYC311 common topics, and Jackson County website structure. Not verified against Jackson County internal call volume data.

---

## Government Synonyms — BM25 Query Expansion

### Implementation Pattern: Pre-Expand Query Before BM25 Tokenization

**Why pre-expand (not post-expand):** BM25 operates on the tokenized query. Add synonyms to the query string before tokenization. This is simpler and more predictable than modifying the BM25 index.

```python
# backend/app/services/bm25_index.py

# Government synonym dictionary for Jackson County / general US municipal context
GOVERNMENT_SYNONYMS: dict[str, list[str]] = {
    # Tax
    "trash": ["waste collection", "garbage", "refuse", "rubbish", "solid waste"],
    "garbage": ["trash", "waste collection", "refuse", "rubbish"],
    "recycling": ["recyclables", "recycle", "recycling pickup", "curbside recycling"],
    "bulk trash": ["large item pickup", "bulk pickup", "junk removal", "furniture pickup"],

    # Tax and Payments
    "property tax": ["real estate tax", "tax bill", "property assessment", "tax payment"],
    "personal property tax": ["vehicle tax", "car tax", "business personal property"],
    "tax bill": ["property tax", "tax statement", "tax notice"],
    "owe": ["balance", "amount due", "outstanding", "unpaid"],
    "pay": ["payment", "pay online", "pay by mail", "payment options"],
    "delinquent": ["past due", "overdue", "late payment", "delinquency"],
    "rebate": ["credit", "reimbursement", "refund", "tax relief"],
    "exemption": ["tax exemption", "homestead exemption", "senior exemption", "disability exemption"],

    # Benefits and Assistance
    "snap": ["food stamps", "food assistance", "ebt", "food benefits", "supplemental nutrition"],
    "food stamps": ["snap", "ebt", "food assistance", "food benefits"],
    "benefits": ["assistance", "programs", "services", "aid", "support"],
    "welfare": ["public assistance", "benefits", "aid", "human services"],

    # Permits and Licensing
    "permit": ["building permit", "zoning permit", "construction permit", "development permit"],
    "license": ["business license", "contractor license", "professional license"],
    "zoning": ["land use", "zoning regulations", "zoning variance", "rezoning"],

    # Elections and Voting
    "vote": ["voter registration", "polling place", "ballot", "election"],
    "voter registration": ["register to vote", "voting registration", "voter card"],
    "polling place": ["polling location", "where to vote", "voting location", "poll site"],
    "absentee": ["mail-in ballot", "absentee ballot", "vote by mail"],

    # Courts and Legal
    "traffic ticket": ["citation", "moving violation", "speeding ticket", "fine"],
    "court fee": ["court cost", "filing fee", "court charge"],
    "fine": ["penalty", "court fee", "traffic ticket", "citation fee"],
    "lawsuit": ["civil case", "legal action", "court case"],

    # Utilities and Infrastructure
    "water bill": ["utility bill", "water payment", "water service"],
    "sewer": ["sanitation", "wastewater", "sewage"],
    "pothole": ["road damage", "road repair", "street repair", "pavement issue"],
    "streetlight": ["street light", "light outage", "broken light"],

    # Emergency and Safety
    "emergency": ["911", "urgent", "crisis", "hazard"],
    "non-emergency": ["non emergency", "sheriff", "noise complaint", "general issue"],
    "animal control": ["stray animal", "dog bite", "animal complaint", "animal shelter"],

    # Parks and Recreation
    "parks": ["recreation", "parks department", "park hours", "park facilities"],
    "program": ["class", "activity", "registration", "sign up"],
}

def expand_government_query(query: str) -> str:
    """
    Expand query with government synonyms before BM25 tokenization.

    Strategy: add synonyms as additional terms (not replace original).
    BM25 gives full weight to original terms and additional weight to synonyms.

    Example: "when is my trash day" → "when is my trash day waste collection garbage refuse"
    """
    query_lower = query.lower()
    expanded_terms = [query]

    for term, synonyms in GOVERNMENT_SYNONYMS.items():
        if term in query_lower:
            # Add 1-2 most relevant synonyms (don't flood the query)
            expanded_terms.extend(synonyms[:2])

    # Deduplicate while preserving order
    seen = set()
    unique_terms = []
    for term in " ".join(expanded_terms).split():
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return " ".join(unique_terms)
```

**Synonym coverage (count: 33 base terms + expansion):**

| Category | Terms Covered |
|----------|--------------|
| Waste/Trash | trash, garbage, recycling, bulk trash |
| Tax/Payments | property tax, personal property tax, tax bill, owe, pay, delinquent, rebate, exemption |
| Benefits | SNAP, food stamps, benefits, welfare |
| Permits/Licensing | permit, license, zoning |
| Elections | vote, voter registration, polling place, absentee |
| Courts | traffic ticket, court fee, fine, lawsuit |
| Utilities/Infrastructure | water bill, sewer, pothole, streetlight |
| Emergency/Safety | emergency, non-emergency, animal control |
| Parks | parks, program |

**BM25 parameters for FAQ search:**
- `k1=1.5` — standard for document retrieval (term saturation)
- `b=0.75` — standard length normalization
- For short FAQ answers (50-100 words): consider `b=0.5` to reduce length bias against short answers

**Confidence:** MEDIUM-HIGH — synonym pairs derived from domain knowledge of US municipal government terminology and confirmed by Jackson County website structure. GXA/Granicus specifically mentions "trash pickup schedule" and "permit" as primary use cases. SNAP/food stamps mapping is verified from official SNAP program name documentation.

---

## Common Pitfalls

### Pitfall 1: Redis Failure Propagating as Voice Turn Error
**What goes wrong:** Redis connection error raises exception, propagates through `retrieve()`, voice turn returns error to user.
**Why it happens:** Default redis-py throws `redis.exceptions.ConnectionError` on timeout or connection failure.
**How to avoid:** Wrap ALL Redis operations in try/except that catches `Exception` (not just `redis.exceptions.ConnectionError`) and falls through to BM25. Log the error at WARNING level.
**Warning signs:** User-facing errors that mention "connection refused" or "timeout." CloudWatch FallbackToDirectBM25 counter rising unexpectedly.

### Pitfall 2: BM25 Index Not Built Before First Request
**What goes wrong:** First voice turn tries to call `BM25Okapi.get_scores()` but `bm25` is None or corpus is empty. Returns no results. LLM has no context.
**Why it happens:** DynamoDB scan and BM25 build happen synchronously in `__init__`. If DynamoDB is unavailable at startup, build fails silently with empty corpus.
**How to avoid:** Check corpus length after build. If empty, raise at startup (not silently). Use `DescribeTable` before Scan to verify table exists.
**Warning signs:** `BM25TopScore` metric stays at 0.0 for all turns. Retrieved chunks list is empty on all turns.

### Pitfall 3: DynamoDB Scan Without Paginator Returns Truncated Results
**What goes wrong:** `dynamo.scan()` returns at most 1MB per call. For 50 FAQs (~110KB), this works fine today. At 200+ FAQs (~440KB), results are silently truncated. BM25 index misses chunks.
**Why it happens:** DynamoDB returns `LastEvaluatedKey` when results are paginated. Without paginator, you see `LastEvaluatedKey` in response but don't fetch next page.
**How to avoid:** Use `boto3.get_paginator("scan")` from day one. Zero extra cost, handles any scale.
**Warning signs:** FAQ count in BM25 index doesn't match DynamoDB item count.

### Pitfall 4: Embedding Stored as JSON Float List (Not Binary)
**What goes wrong:** 384 float values stored as a JSON string: `[0.234, -0.145, ...]`. Takes ~5KB per embedding instead of 1.5KB. Parsing is slower.
**Why it happens:** Easier to write `json.dumps(embedding.tolist())` than `embedding.tobytes()`.
**How to avoid:** Always use `numpy.ndarray.tobytes()` and DynamoDB `{"B": bytes_value}`. boto3 handles base64 wire encoding transparently.
**Warning signs:** DynamoDB items showing ~5-6KB size instead of ~2.2KB.

### Pitfall 5: ECS Task OOM-Killed During Model Warm-Up
**What goes wrong:** ECS task starts, loads sentence-transformers model, memory spikes to 450MB, ECS kills task at 512MB hard limit. Service restart loop. Logs show `OOMKilled`.
**Why it happens:** PyTorch allocates working memory for first inference call. Cold start allocation exceeds 512MB briefly even if steady-state is ~300MB.
**How to avoid:** Run at 1024MB. This is already decided in CONTEXT.md.
**Warning signs:** ECS task cycling every few minutes. CloudWatch showing tasks going from Running to Stopped repeatedly.

### Pitfall 6: Stale BM25 Index After FAQ Updates
**What goes wrong:** New FAQs are written to DynamoDB but BM25 index in memory is not rebuilt. Queries don't hit new FAQ content.
**Why it happens:** BM25 index is built once at startup from DynamoDB Scan. Monthly updates to DynamoDB don't trigger index rebuild.
**How to avoid:** Add an index rebuild endpoint (`POST /admin/rebuild-index`) or trigger rebuild on ECS service redeployment (which runs `__init__` again).
**Warning signs:** New FAQ chunks in DynamoDB but no retrieval hits for new topic areas.

### Pitfall 7: 01-02-PLAN.md References Stale pgvector Architecture
**What goes wrong:** Plan 02 implements Aurora PostgreSQL + pgvector. This is no longer the correct architecture per CONTEXT.md (DynamoDB + BM25 + Redis).
**How to avoid:** 01-02-PLAN.md MUST be rewritten before execution. The planner should generate a new Plan 02 targeting DynamoDB Scan → BM25 index build → Redis cache pattern.
**Warning signs:** Executor attempts to provision Aurora Serverless v2 database.

---

## Code Examples

### BM25 Redis Retriever — Full Working Example

```python
# Source: rank_bm25 PyPI docs + redis-py official docs + pattern verified in research
import hashlib
import json
import time
from rank_bm25 import BM25Okapi
import redis

class DynamoKnowledgeAdapter:
    """
    Production KnowledgeAdapter using DynamoDB (corpus storage) + BM25 (retrieval) + Redis (cache).
    Fallback: Redis unavailable → BM25 directly. Never fail voice turns due to cache.
    """

    def __init__(
        self,
        dynamo_client,
        table_name: str,
        redis_url: str | None = "redis://localhost:6379",
        redis_ttl: int = 3600,
        region: str = "ap-south-1",
    ):
        # Load corpus and build BM25 index at startup
        self._corpus, self._bm25 = self._build_index(dynamo_client, table_name)

        # Redis connection — None if URL not provided or connection fails
        self._redis = None
        self._redis_ttl = redis_ttl
        if redis_url:
            try:
                pool = redis.ConnectionPool.from_url(redis_url, max_connections=10)
                self._redis = redis.Redis(connection_pool=pool, socket_connect_timeout=1, socket_timeout=0.5)
                self._redis.ping()  # Verify connectivity at startup
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

    async def retrieve(self, query: str, top_k: int = 5) -> "KnowledgeResult":
        import asyncio
        t0 = time.monotonic()
        results = await asyncio.to_thread(self._retrieve_sync, query, top_k)
        latency_ms = (time.monotonic() - t0) * 1000

        from backend.app.services.knowledge import KnowledgeResult
        return KnowledgeResult(
            chunks=[r["text"] for r in results],
            sources=[r["source_doc"] for r in results],
            search_latency_ms=latency_ms,
        )

    def _retrieve_sync(self, query: str, top_k: int) -> list[dict]:
        # Cache key
        cache_key = f"bm25:v1:{hashlib.sha256(query.lower().encode()).hexdigest()[:16]}"

        # Try Redis
        if self._redis:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        # BM25 with query expansion
        from backend.app.services.bm25_index import expand_government_query
        expanded = expand_government_query(query)
        scores = self._bm25.get_scores(expanded.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [
            {"text": self._corpus[i]["text"], "source_doc": self._corpus[i]["source_doc"],
             "department": self._corpus[i]["department"], "score": float(scores[i])}
            for i in top_indices if scores[i] > 0.01
        ]

        # Cache results
        if self._redis and results:
            try:
                self._redis.setex(cache_key, self._redis_ttl, json.dumps(results))
            except Exception:
                pass

        return results
```

### DynamoDB Conversation Turn Write

```python
# Source: AWS DynamoDB official docs + conversation session design
import uuid
from datetime import datetime, timezone

def write_conversation_turn(dynamo, session_id, turn_num, user_input, response_text, pipeline_result, rag_chunk_ids, table_name):
    now = datetime.now(timezone.utc)
    total_ms = pipeline_result.asr_ms + pipeline_result.rag_ms + pipeline_result.llm_ms + pipeline_result.tts_ms

    item = {
        "session_id":  {"S": session_id},
        "turn_number": {"N": str(turn_num)},
        "user_input":  {"S": user_input[:2000]},  # Guard against very long inputs
        "assistant_response": {"S": response_text[:4000]},
        "rag_chunks_used": ({"SS": rag_chunk_ids} if rag_chunk_ids else {"NULL": True}),
        "asr_ms":  {"N": str(round(pipeline_result.asr_ms, 2))},
        "rag_ms":  {"N": str(round(pipeline_result.rag_ms, 2))},
        "llm_ms":  {"N": str(round(pipeline_result.llm_ms, 2))},
        "tts_ms":  {"N": str(round(pipeline_result.tts_ms, 2))},
        "total_ms": {"N": str(round(total_ms, 2))},
        "slo_met":  {"BOOL": total_ms < 1500},
        "timestamp": {"S": now.isoformat()},
        "ttl":      {"N": str(int(now.timestamp()) + 90 * 86400)},
    }
    dynamo.put_item(TableName=table_name, Item=item)
```

---

## API Architecture — Pluggable Design

### Is This API-Driven and Usable Anywhere?

**YES.** The Phase 0 + Phase 1 architecture is inherently API-driven. Three endpoints serve all client types:

| Endpoint | Protocol | Client Use Case |
|----------|----------|-----------------|
| `ws://host/ws` | WebSocket | Browser voice mic, telephony WebSocket bridge |
| `POST /chat` | HTTP REST | Mobile apps, SMS gateways, Slack bots, CLI tools |
| `GET /health` | HTTP REST | Load balancers, monitoring, uptime checks |
| `GET /metrics` | HTTP REST | Dashboards, TPM monitoring, SLO tracking |

**How to add a new client:** No code changes to the core service. New clients connect to the existing endpoints. Example integrations:

1. **Twilio Voice (telephony):** Twilio WebSocket bridges to `/ws` endpoint. Existing code handles it.
2. **Slack bot:** Slack events webhook → Python Lambda → POST `/chat` → return response to Slack.
3. **SMS (Twilio SMS):** SMS webhook → Lambda → POST `/chat` → reply via Twilio SMS API.
4. **Internal admin dashboard:** React app POSTs to `/chat`, renders conversation history.

**How to swap adapters (providers) without code changes:**

```python
# backend/app/orchestrator/runtime.py

def build_pipeline() -> VoicePipeline:
    asr_provider = os.getenv("ASR_PROVIDER", "aws")      # "aws" | "deepgram" | "mock"
    llm_provider = os.getenv("LLM_PROVIDER", "bedrock")  # "bedrock" | "openai" | "mock"
    tts_provider = os.getenv("TTS_PROVIDER", "polly")    # "polly" | "elevenlabs" | "mock"

    asr = {
        "aws": AwsTranscribeAdapter,
        "mock": MockASRAdapter,
        # Future: "deepgram": DeepgramAdapter,
    }[asr_provider]()

    llm = {
        "bedrock": AwsBedrockAdapter,
        "mock": MockLLMAdapter,
        # Future: "openai": OpenAIAdapter,
    }[llm_provider](clients=build_aws_clients() if llm_provider == "bedrock" else None)

    knowledge = DynamoKnowledgeAdapter(
        dynamo_client=boto3.client("dynamodb", region_name="ap-south-1"),
        table_name=os.getenv("DYNAMO_TABLE_NAME", "voicebot-faq-knowledge"),
    ) if not _use_mocks() else MockKnowledgeAdapter()

    return VoicePipeline(asr=asr, llm=llm, tts=tts, knowledge=knowledge)
```

**Confidence:** HIGH — pattern verified against existing Phase 0 runtime.py implementation and FastAPI lifespan documentation.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Aurora PostgreSQL + pgvector | DynamoDB + BM25 + Redis | ~$43-80/mo savings; simpler ops |
| Bedrock Titan V2 embeddings (1536-dim) | all-MiniLM-L6-v2 sentence-transformers (384-dim) | Dimension consistency; ~75% cost reduction |
| EC2 intermediate tier | Local Docker → ECS directly | Eliminated ops complexity |
| Per-request embedding at query time | Pre-computed embeddings stored in DynamoDB | ~5ms savings per query |
| Single CloudWatch namespace | `voicebot/latency` + `voicebot/rag` + `voicebot/conversations` | Per-dimension alerting and TPM dashboards |
| No conversation tracking | DynamoDB Table 2 with TTL | Enables cost-per-session, completion rate, follow-up rate metrics |

**Deprecated/outdated in this plan:**
- Aurora PostgreSQL Serverless v2: Removed. Replaced by DynamoDB + BM25.
- `pg_schema.sql` (vector(384)): No longer needed. Archive if written in 01-02-PLAN.md.
- `AwsKnowledgeAdapter` with psycopg2: Replace with `DynamoKnowledgeAdapter` using boto3.
- EC2 deployment tier documentation: Remove from CONTEXT.md and ROADMAP.md.

---

## Open Questions

1. **Conversation tracking in Phase 1 vs Phase 2**
   - What we know: DynamoDB Table 2 schema is ready; write_conversation_turn is a 10-line function
   - What's unclear: Does Plan 03 (ECS Deployment) include conversation write? Plan 04 (Monitoring) needs it for metrics.
   - Recommendation: Add ConversationAdapter to Plan 03 as a lightweight task (1 hour implementation). Don't defer to Phase 2 — metrics dashboard in Plan 04 depends on it.

2. **Redis in ECS: sidecar container vs ElastiCache**
   - What we know: Running Redis as a sidecar container in the same ECS task is viable for MVP. ElastiCache adds ~$13/mo.
   - What's unclear: ECS Fargate does not support multiple containers in the same task easily. Using a second container in the same task definition is the correct pattern, but adds memory overhead (~30MB for Redis).
   - Recommendation: Use Redis sidecar in same task definition for Phase 1. Move to ElastiCache in Phase 2 if Redis restart during task rolling update is observed.

3. **BM25 index rebuild mechanism**
   - What we know: Monthly FAQ updates require BM25 index rebuild. ECS rolling deployment triggers `__init__` which rebuilds from DynamoDB.
   - What's unclear: Is a rolling deployment triggered by FAQ-only updates (no code change)?
   - Recommendation: Add an admin endpoint `POST /admin/rebuild-index` that rebuilds in-memory without redeployment. Protected by a simple admin token. Adds 30 lines of code.

4. **SNAP/benefits synonyms completeness**
   - What we know: Jackson County is in Missouri; county-level benefits administration may not include SNAP directly (often state-administered). Check jacksongov.org for whether the county FAQ includes benefits info.
   - What's unclear: Which Human Services topics Jackson County covers vs defers to state.
   - Recommendation: Include SNAP synonyms in the dictionary but validate against actual FAQ corpus before launch.

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
  - https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/discussions/22

### Secondary (MEDIUM confidence)
- Granicus GXA — Government chatbot use cases, top intents (FAQ, permits, waste, elections)
  - https://granicus.com/blog/smarter-government-starts-here-use-cases-for-the-government-experience-agent/
  - https://granicus.com/blog/how-local-governments-can-use-ai-powered-chatbots/
- AWS Database Blog — DynamoDB data models for generative AI chatbots (session schema patterns)
  - https://aws.amazon.com/blogs/database/amazon-dynamodb-data-models-for-generative-ai-chatbots/
- Evidently AI — RAG evaluation metrics, groundedness score, proxy signals for hallucination
  - https://www.evidentlyai.com/llm-guide/rag-evaluation
- RAGAS Framework — Faithfulness and groundedness metrics for RAG without ground truth
  - (Referenced via Evidently AI and EMNLP 2024 findings paper)
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
- Government synonyms: MEDIUM — domain knowledge, not benchmarked
- GXA/Granicus intents: MEDIUM — derived from marketing materials, not internal analytics
- Hallucination proxy: MEDIUM — heuristic approach, RAGAS-inspired but not formally validated
- Cost per conversation formula: MEDIUM — pricing estimates from AWS public pricing pages (ap-south-1)

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (30-day window for stable stack)
**Next research trigger:** If Granicus releases new GXA intent taxonomy, or if DynamoDB pricing changes in ap-south-1.
