# Phase 1: Government Voice Baseline - Context

**Gathered:** 2026-03-09
**Status:** Context locked — architecture updated 2026-03-10 (TWO-TIER ONLY: Local Docker + ECS Fargate; EC2 tier removed; BM25+DynamoDB RAG; 4-plan structure)

<domain>
## Phase Boundary

Implement a runnable MVP web voice bot with RAG knowledge base for Jackson County government FAQs. Uses a **two-tier** deployment strategy:

- **Tier 1 — Local Docker Compose:** Dev and pre-production testing ($0 compute)
- **Tier 2 — ECS Fargate (existing cluster):** Live Jackson County MVP (~$15.50/mo)

**No EC2 tier exists in Phase 1.** EC2 was evaluated and removed from the architecture on 2026-03-10. All cloud traffic runs on ECS Fargate only. A single shared codebase serves both tiers with configuration-only differences (credentials, service endpoints).

RAG inserts between ASR and LLM stages to ground answers in official county documents. Establishes turn latency baseline (<1.5s end-to-end).

</domain>

<decisions>
## Implementation Decisions

### Two-Tier Deployment Strategy (LOCKED)
Same codebase runs in both tiers — only configuration (credentials, service endpoints) changes:

| Tier | Environment | Cost | Purpose |
|------|------------|------|---------|
| Tier 1 | Local Machine (Docker Compose) | $0 compute, ~$5/mo API | Dev, fast iteration |
| Tier 2 | ECS Fargate (existing cluster) | ~$15.50/mo | Live Jackson County MVP |

- **AWS credentials:** Local uses `~/.aws/credentials`, ECS uses IAM roles
- **Service discovery:** Local uses `localhost:PORT`, ECS uses container names (`redis://localhost:6379` within task)

**EC2 tier removed 2026-03-10.** There is no Tier 3. All pre-production testing runs locally via Docker Compose. ECS Fargate is the only cloud deployment target for Phase 1.

### RAG Service Architecture (LOCKED)
**For MVP: all services run in same ECS task to save cost (import as modules, not separate processes)**

Services:
- **Port 8000:** Orchestrator (FastAPI WebSocket — existing Phase 0 service, modified)
- **Port 8001:** Embedding service (all-MiniLM-L6-v2, FastAPI, imported as module in MVP)
- **Port 8002:** BM25 service (stateless reranker, FastAPI, imported as module in MVP)
- **Shared:** Redis cache (local: Redis container; ECS: Redis sidecar in same task)

Upgrade to separate ECS tasks in Phase 2 when independent scaling is needed.

### RAG Stack (LOCKED)
- **Embedding model:** `all-MiniLM-L6-v2` (384-dim, Sentence Transformers, ~5ms inference)
  - Local: runs in-process (free, offline-capable)
  - ECS: runs in same task (no cold starts)
- **Reranking:** BM25 (~1-2ms — pure text matching, no ML inference needed)
  - Why BM25 over pgvector reranking: faster, simpler, no Aurora PostgreSQL cost (~$43-80/mo saved)
- **Caching:** Redis (1ms lookup for repeated queries)
- **Vector storage:** DynamoDB (FAQ text, metadata, pre-computed 384-dim embeddings)
- **PDF storage:** S3 (raw source documents)

### Cost Comparison
| Option | Monthly Cost | Decision |
|--------|--------------|---------|
| Aurora PostgreSQL + pgvector (prev plan) | ~$43-80 | Dropped — overkill for 50 FAQs |
| **DynamoDB + BM25 + Redis (chosen)** | **~$5-15** | Simple, fast, cheap for FAQ scale |
| OpenSearch Serverless | ~$174 | Expensive, not needed |

### Data Pipeline (Monthly Updates)
1. Manual PDF extraction from Jackson County official documents (human-curated)
2. FAQ parser: Extract Q&A pairs from PDFs
3. Semantic chunking: Split into logical chunks
4. Batch embed: Sentence Transformers → 384-dim vectors
5. Store: DynamoDB (text + embeddings + metadata), S3 (raw PDFs)

### RAG Integration Point (LOCKED)
- **LLM:** Claude 3.5 Sonnet
- Modify `LLMAdapter` → `RAGLLMAdapter` (minimal change):
  ```python
  class RAGLLMAdapter(LLMAdapter):
      def __init__(self, rag_service_url):
          self.rag_service = rag_service_url  # http://localhost:8001 or http://rag-service:8001

      def generate(self, user_query, conversation_history):
          rag_result = requests.post(
              f"{self.rag_service}/search",
              json={"query": user_query, "client_id": "jackson-county", "k": 3}
          ).json()
          return claude.messages.create(
              system=f"You are a helpful government assistant.\n\n{rag_result['faq_context']}",
              messages=[{"role": "user", "content": user_query}]
          )
  ```
- Pass top 3 FAQs as context in system prompt
- Always include source attribution in responses

### Latency SLO (LOCKED)
- **Target:** <1.5s turn latency (end-to-end: ASR start → TTS complete)
  - ASR: ~200ms
  - Embed + BM25 + Redis: ~6ms
  - LLM: ~800ms
  - TTS: ~400ms
- Track per-stage breakdowns in CloudWatch (p50, p95, p99)

### Initial Knowledge Corpus
- Jackson County FAQs (2023-2025)
- Permits & forms (planning, zoning, environmental, public works)
- Finance & collections info (tax, vendor, procurement)
- HR, emergency management, elections resources
- ~50 PDFs covering major departments and services

### ECS Resource Requirements (LOCKED — research verified 2026-03-10)
- **ECS task memory: 1024MB** (all-MiniLM-L6-v2 requires ~91MB model + ~150MB PyTorch; 512MB causes OOM)
- **ECS task CPU: 512 units** (upgrade from 256 to handle embedding inference without throttling)
- **Monthly cost: ~$15.50/mo** (up from $8.96/mo at 512MB/256CPU)

### BM25 Accuracy Policy (LOCKED)
- BM25 70-80% recall@5 is acceptable for Phase 1 MVP
- Paraphrase misses (e.g., "what do I owe?" vs "property tax payment") mitigated by system prompt query expansion
- Upgrade path: hybrid semantic + BM25 in Phase 2 if accuracy is insufficient after real user testing
- BM25 actual latency: ~1-2ms (not 0ms — corrected from prior estimate)

### Claude's Discretion
- Exact chunking size and overlap for FAQ splitting
- BM25 scoring parameters (k1, b values)
- Redis TTL for cached query results
- CloudWatch dashboard visualization (per-stage timings, outliers)
- DynamoDB table schema (GSI design for client_id filtering, with boto3 paginator from day one)
- System prompt query expansion wording for paraphrase gap mitigation

</decisions>

<specifics>
## Specific Requirements

- **Monthly Updates:** Knowledge base refreshes monthly with new/updated county documents
- **Offline Capability:** Bot must work locally for development without AWS connectivity
- **Accuracy Focus:** Authoritative, grounded answers from official Jackson County sources
- **Source Attribution:** Responses reference which document/FAQ answered the question (Phase 1: source_doc name; page/section reference deferred to Phase 4)
- **SLO:** <1.5s turn latency measured end-to-end

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 0)
- **ASRAdapter** (backend/app/services/asr.py): Adapter pattern; RAG embedding service follows same pattern
- **VoicePipeline** (backend/app/orchestrator/pipeline.py): Orchestrates ASR → LLM → TTS; RAG inserts between ASR and LLM
- **LLMAdapter**: Minimal modification to `RAGLLMAdapter` — add RAG service call before Claude invocation

### Established Patterns
- Adapter-based service abstraction (Mock + AWS implementations)
- Pipeline stage error handling
- WebSocket streaming for voice I/O

### Integration Points
- `LLMAdapter.generate()` → modified to call RAG service, inject FAQ context into system prompt
- `VoicePipeline` — latency tracking hooks at each stage (ASR, RAG lookup, LLM, TTS)
- Pre-computed embeddings in DynamoDB (no inference at query time for vector lookup)

### New File Structure
```
embedding-service/
  app.py (FastAPI, all-MiniLM-L6-v2)
  Dockerfile
  requirements.txt

bm25-service/
  app.py (FastAPI, BM25 reranker)
  Dockerfile
  requirements.txt

orchestrator/          # Phase 0 backend, modified
  rag_client.py        # new: calls embedding + BM25 services
  Dockerfile

docker-compose.yml     # local dev: all services + Redis
infra/
  ecs_task_definition.json   # ECS task definition (1024MB/512CPU)
  iam_task_role_policy.json  # IAM task role policy
```

</code_context>

<deferred>
## Deferred Ideas

- **VAD/Silence Detection:** Defer to Phase 2 after RAG integration validated
- **Separate ECS tasks per service:** Phase 2 (when independent scaling needed)
- **Multi-language Support:** Future phases
- **Advanced Citation Formatting (page/section refs):** Phase 4 (RAG Scale) — RAG-02 Phase 1 covers source_doc name attribution only
- **Auto-scraping from website:** Manually curated PDFs only; auto-scraper in backlog
- **CrossEncoder reranking:** Phase 2 upgrade path (replace BM25 if accuracy insufficient)

</deferred>

---

**Plan Structure (4 plans):**
- Plan 01: Local System Setup — Docker Compose, AWS creds, Phase 0 integration, SLO <1.5s local
- Plan 02: RAG Services Implementation — embedding service, BM25, Redis cache, S3+DynamoDB pipeline
- Plan 03: ECS Deployment & Integration — task definitions, RAGLLMAdapter, load Jackson County FAQs, E2E test
- Plan 04: Latency Measurement & Monitoring — CloudWatch metrics, SLO baseline, bottleneck optimization

**Next Step:** Run `/gsd:plan-phase 1` to generate detailed implementation plans for all 4 plans.

*Phase: 01-runnable-mvp-web-voice*
*Context gathered: 2026-03-09*
*Last updated: 2026-03-10 (architecture: two-tier ONLY — Local Docker + ECS Fargate; EC2 tier removed)*
