---
phase: 01-runnable-mvp-web-voice
plan: 02
subsystem: api
tags: [bm25, redis, dynamodb, rag, rank-bm25, knowledge-retrieval, bedrock]

# Dependency graph
requires:
  - phase: 01-01
    provides: VoicePipeline, ECS task definition, Docker build working

provides:
  - BM25 index builder (build_bm25_index, bm25_search) with k1=1.5 b=0.75 parameters
  - 32 government synonym pairs via expand_government_query()
  - BM25RedisRetriever with transparent Redis fallback (voice turn NEVER fails on Redis outage)
  - KnowledgeAdapter ABC with DynamoKnowledgeAdapter (DynamoDB paginator) and MockKnowledgeAdapter
  - RAGLLMAdapter: injects top-3 FAQ chunks into Bedrock Converse API system prompt
  - VoicePipeline with per-stage timing (asr_ms, rag_ms, llm_ms, tts_ms)
  - PDF ingest pipeline (extract_chunks_from_pdf) with DynamoDB-ready chunk format
  - all-MiniLM-L6-v2 embed pipeline with lazy-load guard (sentence_transformers NOT eager-loaded)
  - 12 Jackson County FAQ seed entries in sample_faqs.json
  - DynamoDB schema doc: PK=department, SK=chunk_id, page_ref optional (Phase 4 field)

affects:
  - 01-03 (ConversationSession already wired; RAG sources flow through pipeline result)
  - 01-04 (LatencyBuffer uses asr_ms/rag_ms/llm_ms/tts_ms from PipelineResult)
  - 01.5 (agentic voice core builds on KnowledgeAdapter ABC)
  - 04 (hybrid search upgrade uses DynamoDB Binary embeddings stored here)

# Tech tracking
tech-stack:
  added:
    - rank_bm25 (BM25Okapi with k1=1.5 b=0.75)
    - redis (optional, with graceful fallback)
    - pdfplumber (optional, for PDF ingest pipeline)
    - numpy (for embedding bytes conversion)
  patterns:
    - RAG-inject-system-prompt: FAQ context passed as Bedrock system field not user message
    - BM25-redis-transparent-fallback: Redis is optimization not dependency; all errors swallowed
    - dynamo-paginator-mandatory: always use get_paginator("scan") not raw dynamo.scan()
    - lazy-import-guard: sentence_transformers imported only inside load_embedding_model(), never at module level
    - knowledge-adapter-abc: KnowledgeAdapter ABC enables Mock/Dynamo swap via USE_AWS_MOCKS env var
    - page-ref-forward-compat: page_ref field pre-provisioned as null for Phase 1; Phase 4 populates

key-files:
  created:
    - backend/app/services/bm25_index.py
    - backend/app/services/redis_cache.py
    - backend/app/services/knowledge.py
    - knowledge/pipeline/ingest.py
    - knowledge/pipeline/embed.py
    - knowledge/data/local/sample_faqs.json
    - knowledge/data/schemas/dynamo_faq.json
  modified:
    - backend/app/services/llm.py (added system_context param + RAGLLMAdapter)
    - backend/app/orchestrator/pipeline.py (added timing fields + knowledge RAG stage)
    - backend/app/orchestrator/runtime.py (inject MockKnowledgeAdapter or DynamoKnowledgeAdapter)
    - tests/backend/test_knowledge_adapter.py
    - tests/backend/test_bm25_redis.py
    - tests/backend/test_latency_probes.py
    - tests/e2e/test_phase1_roundtrip.py

key-decisions:
  - "BM25 k1=1.5 b=0.75: k1=1.5 gives higher term saturation weight for verbose FAQ answers; b=0.75 is BM25 standard default"
  - "Redis cache key = SHA-256(normalized_query)[:16] with bm25:v1: prefix; TTL=3600s (FAQ content refreshes monthly)"
  - "DynamoDB paginator mandatory: raw dynamo.scan() silently truncates at 1MB; paginator handles LastEvaluatedKey correctly"
  - "RAG context injected into Bedrock system prompt field (not user message): locked architectural decision from CONTEXT.md"
  - "sentence_transformers lazy-loaded inside load_embedding_model() only: prevents 91MB PyTorch model loading on BM25-only import"
  - "page_ref field pre-provisioned as null in Phase 1 schema: Phase 4 hybrid search populates without schema migration"
  - "BM25RedisRetriever never propagates Redis exceptions: Redis is an optimization (1ms cache hit), not a voice turn dependency"
  - "MockKnowledgeAdapter runs real BM25 over sample_faqs.json for offline dev (not just first-N slice)"

patterns-established:
  - "KnowledgeAdapter ABC: swap Mock/Dynamo via USE_AWS_MOCKS env var — same pattern as ASR/LLM/TTS adapters"
  - "Voice pipeline RAG stage: retrieve between ASR and LLM, failure swallowed (RAG failure must never block voice)"
  - "Ingest pipeline: extract_chunks_from_pdf -> embed_and_store_chunks (two-step, lazy model load)"

requirements-completed: [RAG-01, RAG-02, VOIC-03]

# Metrics
duration: 25min
completed: 2026-03-11
---

# Phase 1 Plan 02: RAG Services Layer Summary

**BM25 retrieval (rank_bm25, k1=1.5/b=0.75) with Redis cache fallback, DynamoKnowledgeAdapter using paginator, RAGLLMAdapter injecting FAQ chunks into Bedrock system prompt, and per-stage pipeline timing**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-11T00:00:00Z
- **Completed:** 2026-03-11T00:25:00Z
- **Tasks:** 3
- **Files modified:** 13 (7 created, 6 modified)

## Accomplishments

- Complete RAG services layer: BM25 index builder, Redis cache with transparent fallback, DynamoKnowledgeAdapter (paginator), RAGLLMAdapter (Bedrock system prompt injection)
- 32 government synonym pairs covering trash/tax/benefits/permits/elections/courts/emergency/utilities categories — exceeds >=30 requirement
- VoicePipeline fully instrumented with per-stage timing (asr_ms, rag_ms, llm_ms, tts_ms); runtime.py injects MockKnowledgeAdapter or DynamoKnowledgeAdapter based on USE_AWS_MOCKS
- All 46 tests green (10 new Plan 01-02 tests + 36 pre-existing Phase 0/01-03/01-04 tests)
- PDF ingest pipeline + all-MiniLM-L6-v2 embed pipeline with lazy-load guard confirmed (sentence_transformers not loaded by bm25_index import)

## Task Commits

Each task committed atomically:

1. **Task 1: BM25 index builder and government synonym expansion** - `0481052` (feat: prior session partial)
2. **Task 2: Redis cache, DynamoKnowledgeAdapter, RAGLLMAdapter** - `ecdba98` (feat)
3. **Task 3: Wire RAG into VoicePipeline + ingest pipeline + seed data** - included in `ecdba98` (runtime.py KnowledgeAdapter injection was in prior commits)

**Plan metadata:** to be committed (docs commit)

## Files Created/Modified

- `backend/app/services/bm25_index.py` - BM25Okapi index builder, expand_government_query() with 32 synonym pairs, bm25_search()
- `backend/app/services/redis_cache.py` - BM25RedisRetriever with transparent fallback; SHA-256 cache key; 3600s TTL
- `backend/app/services/knowledge.py` - KnowledgeAdapter ABC, MockKnowledgeAdapter (BM25 over JSON), DynamoKnowledgeAdapter (paginator + BM25 + Redis)
- `backend/app/services/llm.py` - Added system_context parameter to all adapters; RAGLLMAdapter with Bedrock system prompt injection
- `backend/app/orchestrator/pipeline.py` - PipelineResult gains asr_ms/rag_ms/llm_ms/tts_ms; VoicePipeline RAG stage between ASR and LLM
- `backend/app/orchestrator/runtime.py` - build_pipeline() injects MockKnowledgeAdapter (mock mode) or DynamoKnowledgeAdapter (production)
- `knowledge/pipeline/ingest.py` - extract_chunks_from_pdf(): PDF text extraction + department inference + DynamoDB-ready chunk format
- `knowledge/pipeline/embed.py` - load_embedding_model() LAZY import; generate_embedding() 384-dim float32; embed_and_store_chunks() DynamoDB writer
- `knowledge/data/local/sample_faqs.json` - 12 Jackson County FAQ entries (property tax, elections, permits, courts, parks, sheriff, SNAP, etc.)
- `knowledge/data/schemas/dynamo_faq.json` - DynamoDB schema: PK=department, SK=chunk_id, page_ref optional, embedding Binary
- `tests/backend/test_knowledge_adapter.py` - test_bm25_index_builds, test_rag_llm_adapter_injects_context, test_dynamo_uses_paginator, test_faq_item_has_required_fields
- `tests/backend/test_bm25_redis.py` - test_redis_fallback_on_failure, test_expand_government_query_adds_synonyms, test_retrieve_returns_source_attribution
- `tests/backend/test_latency_probes.py` - test_pipeline_result_has_timing_fields

## Decisions Made

- **BM25 k1=1.5 / b=0.75**: k1=1.5 gives higher weight to term frequency for verbose FAQ answers; b=0.75 is BM25 standard. rank_bm25 library used (not hand-rolled — IDF normalization formula is non-trivial).
- **Redis cache key**: SHA-256 of normalized query (first 16 hex chars) with `bm25:v1:` prefix. 3600s TTL because FAQ content changes monthly.
- **DynamoDB paginator mandatory**: raw `dynamo.scan()` silently truncates at 1MB. `get_paginator("scan")` handles `LastEvaluatedKey` correctly for any corpus size.
- **Bedrock system prompt injection**: FAQ context goes in `system=[{"text": ...}]` not prepended to user message. Locked architectural decision from CONTEXT.md.
- **sentence_transformers lazy-load**: import only inside `load_embedding_model()` function body. Prevents 91MB PyTorch model loading whenever any code imports `bm25_index`.
- **page_ref field forward-compat**: pre-provisioned as null in Phase 1. Phase 4 hybrid search populates it without schema migration.
- **Redis is optimization not dependency**: any Redis error (GET or SET) silently falls through to BM25. Voice turns must NEVER fail due to Redis outage.
- **MockKnowledgeAdapter uses real BM25**: runs actual BM25 search over sample_faqs.json (not a first-N slice). Offline dev gets realistic retrieval behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] runtime.py was not injecting KnowledgeAdapter into VoicePipeline**
- **Found during:** Task 3 verification (test_full_voice_turn_returns_sources)
- **Issue:** build_pipeline() called VoicePipeline(asr, llm, tts) without `knowledge=` parameter. Test failed: `Sources list empty -- RAG not wired into pipeline`
- **Fix:** Updated runtime.py to import MockKnowledgeAdapter/DynamoKnowledgeAdapter and pass `knowledge=` to VoicePipeline for both mock and production modes
- **Files modified:** backend/app/orchestrator/runtime.py
- **Verification:** test_full_voice_turn_returns_sources PASSED; 46 total tests green
- **Committed in:** `ecdba98`

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug fix)
**Impact on plan:** Required fix for test correctness; runtime.py was missing the core wiring step.

## Issues Encountered

- Several files (bm25_index.py, knowledge.py, pipeline.py, test files) were already implemented from a prior session execution. Execution continued from where it left off, verifying correctness and completing the remaining uncommitted files.

## User Setup Required

None — no external service configuration required for this plan. DynamoDB ingest is run separately when deploying to production.

## Next Phase Readiness

- RAG stack complete: BM25 + Redis + DynamoDB adapter ready for production ingest
- VoicePipeline timing instrumentation ready for Plan 01-04 CloudWatch metrics
- KnowledgeAdapter ABC ready for Phase 1.5 agentic architecture extension
- Ingest pipeline ready: run `python knowledge/pipeline/ingest.py` on actual Jackson County PDF docs to populate DynamoDB
- To seed DynamoDB: run embed_and_store_chunks() after extracting chunks from PDF files

---
*Phase: 01-runnable-mvp-web-voice*
*Completed: 2026-03-11*
