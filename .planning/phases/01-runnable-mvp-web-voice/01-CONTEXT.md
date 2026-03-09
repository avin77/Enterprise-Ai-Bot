# Phase 1: GXA Voice Baseline - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning (RAG Integration & Latency Measurement pending discussion)

<domain>
## Phase Boundary

Transition the MVP into an authoritative public sector agent by tuning voice activity detection for natural pauses, integrating a local FAQ knowledge base for Jackson County government services, and establishing turn latency baselines (<2.5s). Enables resident-facing demos with accurate, grounded answers from official county documents.

</domain>

<decisions>
## Implementation Decisions

### Knowledge Source Structure (LOCKED)
- **Hybrid Storage Strategy:**
  - **Local Development:** SQLite (embedded, offline-capable) + Markdown files (git-versioned) + Sentence Transformers (free embeddings)
  - **Cloud Production:** DynamoDB (serverless, scalable) + S3 (document storage) + AWS Bedrock/SageMaker (vector embeddings at scale)

- **Data Pipeline (Monthly Updates):**
  1. Manual PDF extraction from Jackson County official documents (no auto-scraper, human-curated)
  2. FAQ parser: Extract Q&A pairs from PDFs and web content
  3. Semantic chunking: Split into logical document chunks
  4. Vector embedding: Use Sentence Transformers locally, Bedrock in cloud
  5. Hybrid indexing: Store in SQLite + DynamoDB with both semantic vectors and full-text index

- **Search Strategy (Hybrid):**
  - Semantic search: Vector similarity for intent matching ("Can I get a permit?" → relevant permits)
  - Exact match: Full-text index for direct keyword lookups
  - Combined ranking: Re-rank results by relevance before passing to LLM

- **Initial Knowledge Corpus:**
  - Jackson County FAQs (2023-2025)
  - Permits & forms (planning, zoning, environmental, public works)
  - Finance & collections info (tax, vendor, procurement)
  - HR, emergency management, elections resources
  - ~50 PDFs covering major departments and services

### Claude's Discretion
- RAG Integration Point (how knowledge reaches LLM) — pending detailed discussion
- Latency Measurement strategy (tracking per-stage timings) — pending detailed discussion
- Exact chunking size and overlap strategy
- Vector embedding model selection (sentence-transformers vs alternatives)
- Caching strategy for frequently accessed FAQs

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
