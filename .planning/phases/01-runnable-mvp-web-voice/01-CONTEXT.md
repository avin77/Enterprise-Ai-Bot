# Phase 1: GXA Voice Baseline - Context

**Gathered:** 2026-03-09
**Status:** Context locked — all gray areas resolved (OpenSearch alternative, embedding strategy, LLM choice, interoperability)

<domain>
## Phase Boundary

Transition the MVP into an authoritative public sector agent by tuning voice activity detection for natural pauses, integrating a local FAQ knowledge base for Jackson County government services, and establishing turn latency baselines (<2.5s). Enables resident-facing demos with accurate, grounded answers from official county documents.

</domain>

<decisions>
## Implementation Decisions

### Knowledge Source Structure (LOCKED)
- **Vector Embedding Strategy (Cost-Optimized):**
  - **Unified embedding model everywhere:** Sentence Transformers `all-MiniLM-L6-v2` (384-dim)
    - Local dev: Sentence Transformers library (free, offline-capable)
    - Cloud production: AWS Lambda compute function (batched, on-demand)
    - **Why:** Avoids dimension mismatch, single index strategy, costs ~$0.01/1000 embeddings vs $0.04 for Titan
    - **Trade-off:** Slightly lower accuracy than Titan V2, acceptable for government FAQs

- **Vector Search Service (Cost-Optimized):**
  - **Aurora PostgreSQL Serverless v2 + pgvector** (~$43/month base + query costs)
    - Single database for documents, metadata, embeddings, full-text index
    - Supports hybrid search (exact match + semantic vector similarity)
    - SQL queries for ranking and filtering
    - Better latency predictability than Lambda scanning
  - **Alternative if cost still high:** DynamoDB scan + rank in Lambda ($5-20/mo, slower but functional)

- **Data Pipeline (Monthly Updates):**
  1. Manual PDF extraction from Jackson County official documents (no auto-scraper, human-curated)
  2. FAQ parser: Extract Q&A pairs from PDFs and web content
  3. Semantic chunking: Split into logical document chunks
  4. Vector embedding: Batch compute using Sentence Transformers (Lambda or local dev) → 384-dim vectors
  5. Hybrid indexing: Store in Aurora PostgreSQL with document text, embeddings, metadata

- **Search Strategy (Hybrid):**
  - Semantic search: pgvector similarity for intent matching ("Can I get a permit?" → relevant permits)
  - Exact match: PostgreSQL full-text search for direct keyword lookups
  - Combined ranking: Query re-ranks results by relevance before passing to LLM

- **Initial Knowledge Corpus:**
  - Jackson County FAQs (2023-2025)
  - Permits & forms (planning, zoning, environmental, public works)
  - Finance & collections info (tax, vendor, procurement)
  - HR, emergency management, elections resources
  - ~50 PDFs covering major departments and services

### RAG Integration Point
- **LLM:** Claude 3.5 Sonnet (balanced cost/speed/accuracy for government FAQs)
- Knowledge context injected into LLM via **System Prompt** (clearest audit trail, supports full FAQ context without token overhead)
- Retrieve relevant FAQ snippets before each LLM call using hybrid search (semantic + exact match)
- Pass top 3-5 most relevant FAQs as context in the system prompt (within 100k token context window)
- Always include source document attribution in the response (e.g., "Per Jackson County FAQs: [document name], [page]")

### System Interoperability
- **KnowledgeAdapter Interface (Portable):**
  - `MockKnowledgeAdapter`: SQLite + Sentence Transformers (dev, offline-capable)
  - `AwsKnowledgeAdapter`: Aurora PostgreSQL + Lambda batching (staging/production)
  - Design with clean interface: `search(query: str, top_k: int) → List[Document]`
  - Allows swapping implementations without changing VoicePipeline code
  - Can be extracted to standalone Python package for reuse in other projects (Phase 3+ decision)
  - VoicePipeline receives KnowledgeAdapter instance via dependency injection

### Latency Measurement
- Track **per-stage breakdowns**: ASR time, RAG lookup time, LLM inference time, TTS synthesis time
- Measure from first audio frame received to final audio output complete
- Store aggregated metrics hourly (p50, p95, p99 latencies) in CloudWatch
- Log detailed per-request timing for analysis and optimization

### Cost Comparison (Staging Environment)
| Option | Monthly Cost | Trade-off |
|--------|--------------|-----------|
| OpenSearch Serverless (research) | ~$174 | Hybrid search, lowest latency, expensive |
| **Aurora PostgreSQL + pgvector (chosen)** | **~$43-80** | Good latency, SQL familiarity, scalable to production |
| DynamoDB + Lambda scan | ~$5-20 | Cheapest, slow search, limited ranking |
| Kendra | ~$230+ | Simplest ops, expensive, overkill for 50 PDFs |

**Chosen approach saves ~$100/month vs OpenSearch, meets latency SLO.**

### Claude's Discretion
- Exact chunking size and overlap strategy for FAQ splitting (balanced for search accuracy)
- Caching strategy for frequently accessed FAQs (Redis or in-process?)
- CloudWatch dashboard visualization (timings, outliers, trend analysis)
- PostgreSQL query tuning (indexes, cost estimation for hybrid search)
- Sentence Transformers version pinning and model cache strategy

</decisions>

<specifics>
## Specific Requirements

- **Monthly Updates:** Knowledge base refreshes monthly with new/updated county documents
- **Offline Capability:** Bot must work locally for development without AWS connectivity
- **Accuracy Focus:** Anyone visiting Jackson County should get authoritative, grounded answers from official sources
- **Multi-Query Support:** Support semantic search + exact match + text lookup together
- **Source Attribution:** Responses should reference which document/FAQ answered the question

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ASRAdapter** (backend/app/services/asr.py): Adapter pattern for ASR implementations; RAG should follow same pattern for knowledge retrieval
- **VoicePipeline** (backend/app/orchestrator/pipeline.py): Orchestrates ASR → LLM → TTS; needs LLM context injection point for RAG
- **LLMAdapter**: Will need modification to accept knowledge context alongside user input

### Established Patterns
- Adapter-based service abstraction (Mock + AWS implementations)
- Pipeline stage error handling
- WebSocket streaming for voice I/O

### Integration Points
- Knowledge retrieval must integrate into **LLMAdapter.generate()** — pass relevant FAQ context to prompt
- Latency tracking should hook into **VoicePipeline** at each stage (ASR, RAG lookup, LLM, TTS)
- Vector embeddings computed offline, stored in SQLite/DynamoDB for inference

### Architecture Decisions Enabled
- RAG lookup can be synchronous (pre-computed vectors) or asynchronous (external service)
- Embedding model choice affects latency vs accuracy tradeoff

</code_context>

<deferred>
## Deferred Ideas

- **VAD/Silence Detection** (Point 1): Defer to Phase 1 Plan 02 or Phase 2 after initial RAG integration
- **Multi-language Support:** Revisit in future phases
- **Advanced Citation Formatting:** Current phase focuses on reference only; rich citations in Phase 4 (RAG Scale)
- **Auto-scraping from website:** Manually curated PDFs only; auto-scraper in backlog for future scalability

</deferred>

---

**Next Steps:**
1. Detailed discussion: RAG Integration Point (how knowledge enters LLM)
2. Detailed discussion: Latency Measurement (tracking 2.5s baseline)
3. Planning: `/gsd:plan-phase 1` with these locked decisions

*Phase: 01-runnable-mvp-web-voice*
*Context gathered: 2026-03-09*
*Last updated: 2026-03-09*
