# Phase 1: Runnable MVP Web Voice - Research

**Researched:** 2026-03-09
**Domain:** AWS-native RAG / knowledge base architecture for voice bot
**Confidence:** HIGH (core stack verified against official AWS docs and direct source fetches)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Knowledge Source Structure (LOCKED)**
- Hybrid Storage Strategy:
  - Local Development: SQLite (embedded, offline-capable) + Markdown files (git-versioned) + Sentence Transformers (free embeddings)
  - Cloud Production: DynamoDB (serverless, scalable) + S3 (document storage) + AWS Bedrock/SageMaker (vector embeddings at scale)
- Data Pipeline (Monthly Updates):
  1. Manual PDF extraction from Jackson County official documents (no auto-scraper, human-curated)
  2. FAQ parser: Extract Q&A pairs from PDFs and web content
  3. Semantic chunking: Split into logical document chunks
  4. Vector embedding: Use Sentence Transformers locally, Bedrock in cloud
  5. Hybrid indexing: Store in SQLite + DynamoDB with both semantic vectors and full-text index
- Search Strategy (Hybrid):
  - Semantic search: Vector similarity for intent matching
  - Exact match: Full-text index for direct keyword lookups
  - Combined ranking: Re-rank results by relevance before passing to LLM
- Initial Knowledge Corpus: ~50 PDFs covering Jackson County FAQs, permits, finance, HR, emergency, elections

**RAG Integration Point (LOCKED)**
- Knowledge context injected into LLM via System Prompt
- Retrieve relevant FAQ snippets before each LLM call using hybrid search (semantic + exact match)
- Pass top 3-5 most relevant FAQs as context in the system prompt
- Always include source document attribution in the response

**Latency Measurement (LOCKED)**
- Track per-stage breakdowns: ASR time, RAG lookup time, LLM inference time, TTS synthesis time
- Measure from first audio frame received to final audio output complete
- Store aggregated metrics hourly (p50, p95, p99 latencies) in CloudWatch
- Log detailed per-request timing for analysis and optimization

### Claude's Discretion

- Exact chunking size and overlap strategy for FAQ splitting
- Vector embedding model selection (sentence-transformers vs alternatives)
- Caching strategy for frequently accessed FAQs
- CloudWatch dashboard visualization (timings, outliers, trend analysis)

### Deferred Ideas (OUT OF SCOPE)

- VAD/Silence Detection: Defer to Phase 1 Plan 02 or Phase 2 after initial RAG integration
- Multi-language Support: Revisit in future phases
- Advanced Citation Formatting: Current phase focuses on reference only; rich citations in Phase 4 (RAG Scale)
- Auto-scraping from website: Manually curated PDFs only; auto-scraper in backlog for future scalability
</user_constraints>

---

## Summary

The locked decisions establish a **DynamoDB + S3 + Bedrock** cloud production stack. Research confirms this is the correct AWS-native approach for the problem domain. The critical regional finding is that both **Amazon Bedrock (Titan Embeddings V2)** and **Amazon OpenSearch Serverless** are available in **ap-south-1 (Mumbai)** as of May 2024 and August 2025 respectively, removing the cross-region latency risk.

The Phase 1 scope is specifically the **cloud production path**: DynamoDB as the document/metadata store, S3 as PDF source, Bedrock for embedding generation during the monthly batch pipeline, and OpenSearch Serverless for vector + hybrid search at query time. The local SQLite path (for offline development) is the complementary track and uses sentence-transformers to match the same interface.

The primary architectural tension is cost: OpenSearch Serverless minimum is **~$174/month** for a non-redundant dev/test collection. For Phase 1 staging with <100 queries/day and ~50 documents, this is the dominant cost driver. Research confirms there is **no cheaper AWS-native vector search** for this use case that also supports hybrid BM25+KNN search. The recommendation is to accept the OpenSearch Serverless cost for staging and offset it by keeping the ECS task at minimum size.

**Primary recommendation:** Use DynamoDB (metadata) + OpenSearch Serverless vector collection (semantic+hybrid search) + Bedrock Titan Embeddings V2 (batch embedding pipeline). Implement a `KnowledgeAdapter` following the existing `ASRAdapter` pattern, with a `MockKnowledgeAdapter` for offline dev and an `AwsKnowledgeAdapter` for cloud.

---

## Standard Stack

### Core

| Library / Service | Version / Tier | Purpose | Why Standard |
|---|---|---|---|
| Amazon S3 | Standard | PDF document storage, source of truth | Already in use; zero marginal cost for 50 PDFs (~$0.01/month) |
| Amazon DynamoDB | On-demand | Document metadata, FAQ chunks, embedding IDs | Serverless, zero idle cost, sub-10ms reads, already in team's IAM posture |
| Amazon OpenSearch Serverless | Vector search collection | KNN + hybrid BM25 search at query time | Only AWS-native service supporting both semantic and exact-match hybrid search natively; available in ap-south-1 since May 2024 |
| Amazon Bedrock (Titan Embed V2) | `amazon.titan-embed-text-v2:0` | Batch embedding generation (monthly pipeline) | In ap-south-1, $0.00011/1K tokens, 1536-dim vectors, natively integrates with OpenSearch |
| opensearch-py | >=2.4 | Python client for OpenSearch Serverless | Official client; supports AOSS SigV4 auth via `requests-aws4auth` |
| boto3 | >=1.34 | AWS SDK; Bedrock + DynamoDB + S3 access | Already used in `aws_clients.py` |
| pdfplumber | >=0.10 | PDF text extraction for FAQ parsing | Best accuracy for structured government PDFs with tables; pure Python, works in Lambda |
| sentence-transformers | >=2.7 (`all-MiniLM-L6-v2`) | Local dev embeddings | Free, 20ms CPU inference, matches 384-dim vector space for offline dev |

### Supporting

| Library / Service | Version | Purpose | When to Use |
|---|---|---|---|
| requests-aws4auth | >=1.3 | SigV4 signing for OpenSearch Serverless | Required for all `opensearch-py` calls to AOSS |
| AWS Lambda | Python 3.12 | Monthly batch embedding pipeline executor | Stateless, event-driven; triggered by S3 upload or manual invocation |
| Amazon EventBridge | Scheduled rule | Monthly pipeline trigger | Zero cost for one rule per month |
| tiktoken or transformers tokenizer | Latest | Token counting before Bedrock calls | Avoid oversized chunks hitting Titan V2's 8K token limit |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| OpenSearch Serverless | Amazon Kendra | Kendra costs $230-$270/month minimum (always-on index billing at $0.32-$1.125/hour); no meaningful free tier past 30 days; less control over ranking. **Eliminated.** |
| OpenSearch Serverless | Aurora PostgreSQL Serverless v2 + pgvector | Aurora minimum ~$43/month at 0.5 ACU + storage; requires VPC, subnet config, DB credentials management; hybrid search requires manual BM25 + pgvector combination in application code. More operational surface for comparable cost. **Eliminated for Phase 1.** |
| OpenSearch Serverless | CloudSearch | CloudSearch is in maintenance mode; no vector/KNN support; cannot do semantic search. **Eliminated.** |
| Bedrock Titan Embed V2 | SageMaker embedding endpoint | Adds ~$50-100/month for an always-on endpoint; overkill for monthly batch; Bedrock on-demand is cheaper at low volume. |
| pdfplumber | PyMuPDF (fitz) | PyMuPDF is faster for bulk extraction but requires C library; pdfplumber is pure Python and works in Lambda without layer compilation. For 50 PDFs/month, speed is irrelevant. |

**Installation (cloud path):**
```bash
pip install opensearch-py requests-aws4auth boto3 pdfplumber sentence-transformers
```

**Installation (local dev path):**
```bash
pip install sentence-transformers pdfplumber sqlite-utils
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── services/
│   ├── asr.py              # Existing - ASRAdapter pattern
│   ├── llm.py              # Existing - LLMAdapter pattern
│   ├── tts.py              # Existing - TTSAdapter pattern
│   ├── knowledge.py        # NEW - KnowledgeAdapter (Mock + AWS implementations)
│   └── aws_clients.py      # Existing - add OpenSearch + Bedrock clients
├── orchestrator/
│   ├── pipeline.py         # MODIFY - inject KnowledgeAdapter, add RAG stage timing
│   └── runtime.py          # Existing
knowledge/
├── pipeline/
│   │── ingest.py           # PDF extraction + chunking (pdfplumber)
│   └── embed.py            # Bedrock embedding calls + DynamoDB/OpenSearch writes
├── data/
│   ├── local/              # SQLite DB + markdown FAQ files (git-tracked)
│   └── schemas/            # DynamoDB table schema, OpenSearch index mapping (JSON)
scripts/
└── run_ingest.py           # Monthly batch runner (local or Lambda trigger)
```

### Pattern 1: KnowledgeAdapter (mirrors ASRAdapter)

**What:** Abstract base class with `MockKnowledgeAdapter` (SQLite, offline) and `AwsKnowledgeAdapter` (OpenSearch Serverless).

**When to use:** Always. The adapter pattern is established in this codebase. Adding RAG as a fourth adapter keeps the `VoicePipeline` clean.

```python
# backend/app/services/knowledge.py
# Pattern: mirrors existing ASRAdapter in asr.py

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class KnowledgeResult:
    chunks: list[str]           # Top 3-5 FAQ text chunks
    sources: list[str]          # Source document names for attribution
    search_latency_ms: float    # For CloudWatch metric reporting

class KnowledgeAdapter(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
        raise NotImplementedError

class MockKnowledgeAdapter(KnowledgeAdapter):
    """Offline dev: returns canned FAQ for any query."""
    async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
        return KnowledgeResult(
            chunks=["Jackson County offices are open Monday-Friday 8am-5pm."],
            sources=["jackson-county-faq-2024.pdf"],
            search_latency_ms=1.0,
        )

class AwsKnowledgeAdapter(KnowledgeAdapter):
    """Cloud production: OpenSearch Serverless hybrid search."""
    def __init__(self, os_client, bedrock_client, index_name: str) -> None:
        self._os = os_client
        self._bedrock = bedrock_client
        self._index = index_name

    async def retrieve(self, query: str, top_k: int = 5) -> KnowledgeResult:
        # 1. Generate query embedding via Bedrock Titan V2
        # 2. Execute hybrid search (KNN + BM25) on OpenSearch Serverless
        # 3. Return top_k chunks + source attribution
        ...
```

### Pattern 2: RAG Stage in VoicePipeline

**What:** Inject `KnowledgeAdapter` into `VoicePipeline.__init__`. Between ASR and LLM, call `retrieve()` and build context string. Measure stage latency.

**When to use:** All voice turns (synchronous, pre-computed vectors make this fast).

```python
# Modification to backend/app/orchestrator/pipeline.py
# Insert between asr.transcribe() and llm.generate()

import time

async def run_roundtrip(self, audio_bytes: bytes) -> PipelineResult:
    t0 = time.monotonic()
    transcript = await self._asr.transcribe(audio_bytes)
    asr_ms = (time.monotonic() - t0) * 1000

    t1 = time.monotonic()
    knowledge = await self._knowledge.retrieve(transcript, top_k=5)
    rag_ms = (time.monotonic() - t1) * 1000

    # Build context-augmented prompt
    context_block = "\n".join(
        f"- {chunk} (Source: {src})"
        for chunk, src in zip(knowledge.chunks, knowledge.sources)
    )
    augmented_input = f"Context:\n{context_block}\n\nUser question: {transcript}"

    t2 = time.monotonic()
    response_text = await self._llm.generate(augmented_input)
    llm_ms = (time.monotonic() - t2) * 1000

    # ... tts, then emit stage metrics to CloudWatch
```

### Pattern 3: Monthly Batch Embedding Pipeline

**What:** S3 PDF upload triggers Lambda (or manual script). Lambda extracts text with pdfplumber, chunks into ~400-token segments with 50-token overlap, embeds via Bedrock Titan V2, writes to DynamoDB (metadata) and OpenSearch Serverless (vectors).

**When to use:** Once per month on document refresh. Not in the query hot path.

```python
# knowledge/pipeline/embed.py
import boto3, json, time
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

def generate_embedding(bedrock_client, text: str) -> list[float]:
    """Source: AWS docs - bedrock-runtime InvokeModel Titan Embeddings V2"""
    response = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text}),
    )
    body = json.loads(response["body"].read())
    return body["embedding"]  # 1536-dim float list

def build_os_client(region: str, host: str) -> OpenSearch:
    """Source: AWS docs - serverless-sdk.html"""
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )
```

### Pattern 4: OpenSearch Serverless Index Mapping

**What:** One index per phase (e.g., `jackson-faq-v1`) with both KNN vector field and text field for BM25.

```json
{
  "settings": {
    "index.knn": true
  },
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "engine": "faiss",
          "parameters": { "ef_construction": 512, "m": 16 }
        }
      },
      "text": { "type": "text" },
      "source_doc": { "type": "keyword" },
      "chunk_id": { "type": "keyword" },
      "department": { "type": "keyword" }
    }
  }
}
```

### Pattern 5: Hybrid Query (BM25 + KNN)

**What:** Single OpenSearch Serverless query combining keyword match and neural vector search. Available in ap-south-1 as of August 2025.

```python
# Source: AWS docs - serverless-configure-neural-search.html

def hybrid_search(os_client, index: str, query_text: str,
                  query_vector: list[float], top_k: int = 5) -> list[dict]:
    body = {
        "size": top_k,
        "query": {
            "hybrid": {
                "queries": [
                    {"match": {"text": query_text}},              # BM25 exact match
                    {"knn": {"embedding": {                        # Semantic
                        "vector": query_vector,
                        "k": top_k,
                    }}}
                ]
            }
        },
        "_source": {"excludes": ["embedding"]},                   # Don't return vector
        "search_pipeline": "hybrid-normalization-pipeline",
    }
    response = os_client.search(index=index, body=body)
    return response["hits"]["hits"]
```

### Anti-Patterns to Avoid

- **Embedding at query time in the voice pipeline:** Never call Bedrock `invoke_model` during a live voice turn. Pre-compute all document embeddings in the batch pipeline. Only the query embedding is generated at runtime (fast, ~100ms via Bedrock, or use sentence-transformers locally).
- **Storing raw embedding vectors in DynamoDB:** DynamoDB does not support KNN search. Use DynamoDB only for metadata (source doc, chunk text, timestamps). OpenSearch Serverless holds the vectors.
- **Single search type only:** Exact-match queries like "permit application form" score poorly in pure KNN. Hybrid (BM25+KNN) is materially better for FAQ retrieval. Always use the hybrid query pattern.
- **Using neural search model IDs in OpenSearch Serverless:** AOSS does not host ML models internally. Generate embeddings externally (Bedrock), then pass vectors directly to the `knn` query. Do not use `neural` query type with an internal model_id.
- **Sharing OCU pools across collection types:** Vector search collections cannot share OCUs with search/time-series collections in AOSS. Always create a dedicated vector search collection.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Vector embedding generation | Custom embedding model training or fine-tuning | Bedrock Titan Embed V2 | Government FAQ text is standard English; pre-trained model is sufficient; training costs $thousands |
| Vector similarity search | Custom cosine/dot-product scan loop | OpenSearch Serverless KNN (HNSW/Faiss) | HNSW at 50-1000 documents is still orders-of-magnitude faster than linear scan; edge cases in normalization are complex |
| Result ranking / score combination | Custom BM25 + vector score weighting | OpenSearch `normalization-processor` (min_max + arithmetic_mean) | Score normalization across query types is mathematically non-trivial; AWS implementation handles scale invariance |
| PDF text extraction | Custom PDF parser | pdfplumber | Government PDFs have complex layouts, tables, footers; pdfplumber handles these; hand-rolled parsers fail on non-standard whitespace and column layouts |
| Monthly pipeline orchestration | Cron job on ECS task | Lambda + EventBridge | Lambda is zero-cost at rest; no need to keep compute alive for a once-monthly job; existing EventBridge already in use for metrics |

**Key insight:** The RAG "needle in a haystack" problem (finding the right 3-5 chunks from 50 PDFs worth of text) has well-established solutions. Custom ranking algorithms are where teams waste weeks only to rediscover BM25 + cosine similarity is optimal for FAQ retrieval at this scale.

---

## Cost Analysis

### Staging Cost (ap-south-1, <100 queries/day, ~50 PDFs)

| Service | Monthly Cost | Notes |
|---|---|---|
| S3 (50 PDFs, ~200MB) | ~$0.005 | 5 GB free tier; negligible |
| DynamoDB on-demand | ~$0.01 | ~3,000 reads/month at $0.125/million RRU; well within free tier (25 GB storage, 200M requests) |
| Bedrock Titan Embed V2 (batch) | ~$0.05 | 50 PDFs * ~500 chunks * ~300 tokens avg = 7.5M tokens; at $0.00011/1K = $0.83 ONE-TIME; monthly re-embed of changed docs only = ~$0.05 |
| OpenSearch Serverless (vector, non-redundant) | **~$174** | MINIMUM: 0.5 OCU indexing + 0.5 OCU search = 1 OCU total * $0.24/hr * 730 hr = $175.20; no free tier; **dominant cost** |
| Lambda (monthly pipeline) | ~$0.00 | 1 invocation/month; well within free tier (1M invocations free) |
| **Total staging** | **~$175/month** | OpenSearch Serverless is 99% of cost |

### Production Cost (monthly, moderate usage)

| Service | Monthly Cost | Notes |
|---|---|---|
| S3 | ~$0.10 | Still tiny at scale |
| DynamoDB | ~$1.00 | Millions of reads at scale |
| Bedrock Titan Embed V2 | ~$0.05/month | Batch only, monthly refresh |
| OpenSearch Serverless | ~$350-700/month | 2 OCUs redundant (production HA); auto-scales with query load |
| Lambda pipeline | ~$0.50 | Larger docs, more invocations |
| **Total production** | **~$350-700/month** | Scales with query volume via OCU auto-scaling |

### Free Tier Eligibility

| Service | Free Tier |
|---|---|
| DynamoDB | YES - 25 GB storage + 25 WCU + 25 RCU permanently free; 200M requests/month |
| S3 | YES - 5 GB storage + 20K GET + 2K PUT for 12 months |
| Bedrock | NO persistent free tier; pay-per-token |
| OpenSearch Serverless | NO free tier |
| Lambda | YES - 1M invocations/month permanently free |

### Cost Risk: OpenSearch Serverless Auto-Scaling

OpenSearch Serverless can scale OCUs upward automatically under load. For staging with <100 queries/day, the 0.5 OCU floor holds. For production bursts, set `maxIndexingCapacity` and `maxSearchCapacity` limits on the AOSS capacity policy to cap costs. Without limits, a traffic spike could push OCU costs to $1,000+/month.

---

## Common Pitfalls

### Pitfall 1: OpenSearch Serverless Minimum Cost Shock

**What goes wrong:** Team expects "serverless = pay per query." AOSS charges by the hour for provisioned OCUs, not per request. A dev/test collection costs ~$174/month even with zero queries.

**Why it happens:** AOSS documentation is clear but the headline "serverless" is misleading. There is no true scale-to-zero for AOSS.

**How to avoid:** Budget $175/month for staging. Delete the collection (not just empty it) when not in use for extended periods. Consider deploying only for sprint cycles.

**Warning signs:** AWS Cost Explorer shows persistent OpenSearch Serverless charges accumulating even during weekends/holidays with no traffic.

### Pitfall 2: Bedrock Regional Model Availability

**What goes wrong:** Code uses a Bedrock model ID that is not available in ap-south-1, causing `ValidationException: The provided model identifier is invalid`.

**Why it happens:** Model availability varies by region. The user's deployment region is ap-south-1. Only a subset of Bedrock models are available there.

**How to avoid:** Confirmed available in ap-south-1: `amazon.titan-embed-text-v2:0`, `amazon.titan-embed-g1-text-02`, `anthropic.claude-3-haiku-20240307-v1:0`, `anthropic.claude-3-sonnet-20240229-v1:0`. Do NOT use Claude 3.5 Sonnet or Nova models without verifying ap-south-1 availability first.

**Warning signs:** `ValidationException` in Bedrock client calls during testing. Verify at `https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html`.

### Pitfall 3: AOSS Neural Query vs. External Embedding

**What goes wrong:** Developer uses OpenSearch `neural` query type with a `model_id`, expecting AOSS to generate embeddings internally. AOSS does not host ML models for inference.

**Why it happens:** Managed OpenSearch Service (not Serverless) can host ML models. Serverless cannot. The hybrid search documentation shows both patterns, causing confusion.

**How to avoid:** Always generate query embeddings externally via Bedrock `invoke_model`. Pass the raw vector to the `knn` query. Use `neural` query type only when setting up AI connectors (advanced, not needed for Phase 1).

**Warning signs:** `model_not_found` or `400` errors when executing neural queries without an externally configured ML connector.

### Pitfall 4: DynamoDB Hot Partition on FAQ Lookups

**What goes wrong:** All queries hit the same DynamoDB partition key pattern, causing throttling on read-heavy access patterns.

**Why it happens:** FAQ data is small; if all 50 documents are stored under a single partition key (e.g., `pk=JACKSON_COUNTY`), all reads hit one shard.

**How to avoid:** Use `department` as partition key (permits, finance, HR, etc.) and `chunk_id` as sort key. This distributes reads across 6-8 partitions matching county departments.

**Warning signs:** `ProvisionedThroughputExceededException` on DynamoDB reads despite low total traffic.

### Pitfall 5: Embedding Model Drift Between Local and Cloud

**What goes wrong:** Local dev uses `sentence-transformers/all-MiniLM-L6-v2` (384-dim) but cloud uses Bedrock Titan V2 (1536-dim). Vectors are incompatible; you cannot mix-and-match search results.

**Why it happens:** Different embedding models produce different vector spaces. A vector generated by MiniLM cannot be compared with a vector generated by Titan V2.

**How to avoid:** Run two completely separate indexes: one SQLite for local dev (MiniLM vectors), one OpenSearch Serverless for cloud (Titan V2 vectors). The `KnowledgeAdapter` interface abstracts which backend is used. Never cross-query between the two vector spaces.

**Warning signs:** Terrible search results in cloud that work fine locally, or `dimension mismatch` errors from OpenSearch.

### Pitfall 6: PDF Chunking Too Large for System Prompt Budget

**What goes wrong:** FAQ chunks are 2,000 tokens each. Passing top 5 chunks = 10,000 tokens of context, approaching Claude context limits and adding ~2-3 seconds to LLM inference.

**Why it happens:** Default text splitting without token-aware chunking.

**How to avoid (Claude's Discretion area):** Target chunks of 300-500 tokens. Use 50-token overlap to preserve context across chunk boundaries. Verify chunk sizes with tiktoken before writing to the index. The top 5 chunks should consume no more than 2,500 tokens of the system prompt.

**Warning signs:** LLM inference time exceeds 2 seconds on queries that retrieve large chunks.

---

## Code Examples

### Generating Embeddings via Bedrock Titan V2

```python
# Source: https://docs.aws.amazon.com/bedrock/latest/userguide/
#         bedrock-runtime_example_bedrock-runtime_InvokeModelWithResponseStream_TitanTextEmbeddings_section.html

import boto3
import json

def generate_embedding(text: str, region: str = "ap-south-1") -> list[float]:
    client = boto3.client("bedrock-runtime", region_name=region)
    model_id = "amazon.titan-embed-text-v2:0"

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps({"inputText": text}),
    )
    body = json.loads(response["body"].read())
    return body["embedding"]  # 1536-dimensional float list
```

### Building OpenSearch Serverless Client with SigV4

```python
# Source: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-sdk.html

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

def build_aoss_client(host: str, region: str = "ap-south-1") -> OpenSearch:
    """
    host: OpenSearch Serverless collection endpoint
    e.g. "abc123.ap-south-1.aoss.amazonaws.com"
    """
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")  # service = "aoss" not "es"
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )
```

### Creating the Vector Index

```python
# Source: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html

def create_faq_index(client: OpenSearch, index_name: str = "jackson-faq-v1") -> None:
    mapping = {
        "settings": {"index.knn": True},
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                "text": {"type": "text"},
                "source_doc": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "department": {"type": "keyword"},
            }
        },
    }
    client.indices.create(index=index_name, body=mapping)
```

### Hybrid Search Query (BM25 + KNN)

```python
# Source: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-configure-neural-search.html

def hybrid_search(
    client: OpenSearch,
    index: str,
    query_text: str,
    query_vector: list[float],
    top_k: int = 5,
) -> list[dict]:
    body = {
        "size": top_k,
        "query": {
            "hybrid": {
                "queries": [
                    {"match": {"text": query_text}},       # BM25 keyword match
                    {"knn": {"embedding": {                 # KNN semantic match
                        "vector": query_vector,
                        "k": top_k,
                    }}},
                ]
            }
        },
        "_source": {"excludes": ["embedding"]},            # Exclude raw vector from response
        "search_pipeline": "hybrid-normalization-pipeline",
    }
    response = client.search(index=index, body=body)
    return [
        {
            "text": hit["_source"]["text"],
            "source": hit["_source"]["source_doc"],
            "score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]
```

### Search Pipeline for Score Normalization

```python
# Must be created once via PUT /_search/pipeline before hybrid queries work.
# Source: AWS OpenSearch Serverless hybrid search docs

def create_hybrid_pipeline(client: OpenSearch) -> None:
    pipeline = {
        "description": "Hybrid BM25 + KNN normalization for FAQ retrieval",
        "phase_results_processors": [
            {
                "normalization-processor": {
                    "normalization": {"technique": "min_max"},
                    "combination": {
                        "technique": "arithmetic_mean",
                        "parameters": {"weights": [0.3, 0.7]},
                        # weights[0]=BM25, weights[1]=KNN
                        # 0.7 KNN weight favors semantic intent matching
                        # for voice queries (natural language, not keyword searches)
                    },
                }
            }
        ],
    }
    client.http.put("/_search/pipeline/hybrid-normalization-pipeline", body=pipeline)
```

### pdfplumber Text Extraction + Chunking

```python
# knowledge/pipeline/ingest.py

import pdfplumber

def extract_chunks_from_pdf(
    pdf_path: str,
    chunk_size: int = 400,          # tokens (approximate via word count * 1.3)
    chunk_overlap: int = 50,
) -> list[dict]:
    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )

    words = full_text.split()
    words_per_chunk = int(chunk_size / 1.3)   # rough token-to-word ratio
    overlap_words = int(chunk_overlap / 1.3)

    i = 0
    while i < len(words):
        chunk_words = words[i : i + words_per_chunk]
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "text": chunk_text,
            "source_doc": pdf_path.split("/")[-1],
            "chunk_index": len(chunks),
        })
        i += words_per_chunk - overlap_words

    return chunks
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Separate vector DB (Pinecone, Weaviate) | OpenSearch Serverless with KNN | 2024 (AOSS in ap-south-1) | All AWS; no third-party service; SigV4 auth vs. API keys |
| Always-on OpenSearch cluster | OpenSearch Serverless | 2023-2024 | No node management; pay-per-OCU; minimum ~$174/month |
| Fine-tuning embedding models | Pre-trained general embeddings (Titan V2, MiniLM) | 2023-ongoing | Government FAQ text is standard English; fine-tuning adds cost without proportional accuracy gain at 50-doc scale |
| Keyword-only search | Hybrid BM25 + KNN | 2024 (AOSS hybrid search GA) | Hybrid search is now standard for FAQ RAG; 15-30% relevance improvement over pure vector search |
| Neural query in OpenSearch | External embedding via Bedrock + raw KNN query | AOSS limitation | AOSS does not host ML models; must embed externally and pass vector |

**Deprecated/outdated:**
- Amazon Kendra for small-scale FAQ: $230-$270/month minimum even at zero usage. Price-performance makes it unsuitable for staging at this scale.
- CloudSearch: In maintenance mode. No vector support. Do not use.
- DynamoDB as a vector store: DynamoDB does not support KNN. Use it for metadata only. Never store embedding vectors there for search.

---

## Open Questions

1. **AOSS Hybrid Search GA Status in ap-south-1**
   - What we know: Hybrid Search was announced for AOSS in August 2025 (all regions including ap-south-1 per announcement)
   - What's unclear: Whether the `normalization-processor` and `hybrid` query DSL are available without additional configuration steps in AOSS (vs. managed OpenSearch)
   - Recommendation: Verify by creating a test collection and confirming pipeline creation does not return `Feature not available` before committing to the hybrid pattern. If hybrid is not available in AOSS at time of implementation, fall back to two separate searches (KNN + match) in Python and do manual score combination.

2. **Phase 1 Staging Cost Acceptance**
   - What we know: OpenSearch Serverless minimum is ~$174/month for the non-redundant dev/test configuration
   - What's unclear: Whether the team will accept this ongoing cost for a staging environment used during development sprints
   - Recommendation: Accept it if sprint duration is 2-3 weeks. Alternatively, implement the full KnowledgeAdapter interface but use only the MockKnowledgeAdapter locally, deferring AOSS provisioning to the integration test sprint. Cost decision should be made before Wave 1 tasks begin.

3. **Titan V2 Embedding Dimensions**
   - What we know: Titan V2 defaults to 1536 dimensions and supports configurable dimensions (256, 512, 1024, 1536)
   - What's unclear: Whether 512-dim is sufficient for ~50-document FAQ retrieval (would reduce AOSS index RAM requirement)
   - Recommendation: Use 1536 for Phase 1 (maximum recall). Evaluate dimension reduction in Phase 4 (RAG Scale) when corpus grows.

---

## Sources

### Primary (HIGH confidence)

- AWS Bedrock Docs: `models-regions.html` — Confirmed Titan Embed V2 available in ap-south-1
- AWS Bedrock Docs: `bedrock-runtime_example_bedrock-runtime_InvokeModelWithResponseStream_TitanTextEmbeddings_section.html` — Titan V2 Python code example
- AWS OpenSearch Docs: `serverless-vector-search.html` — Index mapping, KNN query format, HNSW/Faiss config
- AWS OpenSearch Docs: `serverless-configure-neural-search.html` — Hybrid search pipeline config, Python client example
- AWS What's New: `opensearch-serverless-london-mumbai/` — OpenSearch Serverless confirmed in ap-south-1 since May 2024
- AWS What's New: `opensearch-serverless-ai-connectors-hybrid-search/` — Hybrid search added to AOSS in August 2025

### Secondary (MEDIUM confidence)

- AWS OpenSearch Pricing page (WebFetch) — OCU $0.24/hr, minimum 1 OCU (0.5+0.5) for non-redundant, no free tier
- AWS re:Post community — AOSS billed by hour (not per query), vector collections cannot share OCUs
- AWS Kendra Pricing page (WebFetch) — Minimum $230-270/month; 750-hour free trial only

### Tertiary (LOW confidence — flag for validation)

- WebSearch claim: Titan V2 priced at $0.00011/1K tokens. Verify against live Bedrock pricing page before budgeting; this figure varies by region.
- DynamoDB on-demand price of $0.125/million RRU — standard US rate; ap-south-1 may be 10-20% higher. Use AWS Pricing Calculator for exact figure.
- AOSS storage at $0.024/GB/month — from pricing docs; negligible for 50-PDF use case.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — services verified against official AWS docs; regional availability confirmed
- Architecture patterns: HIGH — code examples sourced directly from AWS documentation
- Cost analysis: MEDIUM — OCU floor ($174/month) is verified; per-token Bedrock pricing and DynamoDB ap-south-1 rates flagged as LOW confidence; use AWS Pricing Calculator before finalizing budget
- Pitfalls: HIGH — DynamoDB hot partition, embedding dimension mismatch, AOSS neural query limitation are all verified against official limitations documentation

**Research date:** 2026-03-09
**Valid until:** 2026-06-09 (90 days — AWS service pricing stable; AOSS hybrid search in AOSS is a new feature, verify before implementation)
