# Requirements: Enterprise AI Voice Bot (GXA / Granicus)

**Defined:** 2026-02-28
**Updated:** 2026-03-10 — added AGENT-* and updated OBS-* for multi-agent agentic architecture
**Core Value:** Deliver fast, secure, and auditable voice conversations that agencies can trust in production.

## v1 Requirements

### Platform and Security

- [ ] **PLAT-00**: MVP backend is deployable to AWS us-east-1 for development validation.
- [ ] **PLAT-01**: Platform provisions private networking, service endpoints, and encrypted storage in AWS us-east-1.
- [ ] **PLAT-02**: IAM roles enforce least privilege with explicit permission boundaries.
- [ ] **PLAT-03**: Security baseline includes threat model v1, authz matrix, and log retention policy.
- [ ] **PLAT-04**: CI enforces formatting, IaC/security scans, and dependency/SAST checks.

### Contracts and Interfaces

- [ ] **API-00**: Backend exposes `/ws`, `/chat`, and `/health` endpoints for MVP interactions.
- [ ] **API-01**: REST endpoints for auth, sessions, knowledge, metrics, and callbacks are documented in OpenAPI.
- [ ] **API-02**: WebSocket message schemas are versioned and validated for all client/server events.
- [ ] **API-03**: Error responses include standardized code, message, trace_id, retryable, and details fields.
- [ ] **API-04**: Server enforces auth scopes for endpoints, WS messages, and tool execution.

### Voice Experience

- [ ] **VOIC-01**: Web client streams microphone audio over authenticated WebSocket and receives partial transcript updates.
- [ ] **VOIC-02**: Orchestrator streams ASR to LLM to TTS and starts bot audio before full response completion.
- [ ] **VOIC-03**: Voice sessions satisfy latency SLO targets for first partial, first audio, and turn latency.
- [ ] **VOIC-04**: Guardrails scrub or block unsafe/PII-sensitive content before final output.

### Observability and Evaluation

- [ ] **OBS-01**: OpenTelemetry traces and dashboards expose latency, reliability, cost, and safety metrics.
- [ ] **OBS-02**: Golden dataset of at least 50 curated conversations with gold-label routing, source, and expected answer.
- [ ] **OBS-03**: Replay harness computes WER, intent match, citation quality, hallucination, and latency metrics.
- [ ] **OBS-04**: Agent trace event emitted every turn: session_id, turn_id, intent, intent_confidence, routing_decision, retrieved_doc_ids, llm_prompt_tokens, llm_response_tokens, llm_latency_ms, tool_calls, total_latency_ms.
- [ ] **OBS-05**: Eval dashboard `voice-bot-mvp-evals` with per-run pass/fail badge, filter by date + last 2h, sortable metric table. Each eval script uses fixed seed for deterministic results.
- [ ] **OBS-06**: Intent confusion matrix: per-intent precision/recall logged per turn, aggregated weekly in CloudWatch `IntentPrecision/{intent_name}`. Fallback path triggers when confidence < 0.7.
- [ ] **OBS-07**: Cost per conversation breakdown: compute_cost_usd + llm_cost_usd + storage_cost_usd. Alert fires if cost_per_turn > 2× baseline_expected_cost.

### Agent Architecture

- [ ] **AGENT-01**: Orchestrator+Intent Agent (Claude-backed) routes each turn, logs intent label and confidence score per turn.
- [ ] **AGENT-02**: Retrieval Agent (Claude-backed) wraps BM25+DynamoDB RAG, returns top-3 chunks with source attribution.
- [ ] **AGENT-03**: Response Agent (Claude-backed) synthesizes grounded final answer with citations from retrieved context.
- [ ] **AGENT-04**: Memory Store persists conversation sessions in DynamoDB (session_id PK, turn_timestamp SK with hashed prefix, TTL 90 days); Orchestrator injects last 5 turns into context.
- [ ] **AGENT-05**: Tool Agent executes municipal tools (property lookup, utility, permits); mock in Phase 1.5, real in Phase 5.
- [ ] **AGENT-06**: Supervisor Agent vetoes unsafe tool plans and responses; outputs signed audit trail with decision reason for every veto.

### RAG and Knowledge

- [ ] **RAG-01**: ETL pipeline ingests S3 documents (PDFs) into DynamoDB + BM25 index with required metadata fields (source_doc, department, chunk_id, text, embedding binary, created_at).
- [ ] **RAG-02**: Retrieval-augmented responses include citations to source documents with page/section reference.
- [ ] **RAG-03**: Tooling supports property lookup and permit status through authenticated municipal interfaces.
- [ ] **RAG-04**: Hybrid retrieval: BM25 initial candidate set re-ranked by embedding similarity in Phase 4; per-candidate scores logged.

### Resilience and Cost Controls

- [ ] **REL-01**: Runtime applies retries/backoff and circuit breakers for external dependency failures.
- [ ] **REL-02**: Service degrades gracefully to text-only mode during speech subsystem issues.
- [ ] **REL-03**: Budget thresholds and per-session usage caps trigger cost protection actions.

## v2 Requirements

### Future Expansion

- **FUT-01**: Support telephony/IVR channels.
- **FUT-02**: Add multi-language support beyond en-US.
- **FUT-03**: Introduce full multi-tenant data and auth isolation.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native mobile apps | Web-first delivery for MVP speed and focus |
| Telephony/IVR in v1 | Deferred until web voice reliability is proven |
| EC2 deployment tier | Removed 2026-03-10 — 2-tier (Local + ECS) is sufficient |
| Aurora PostgreSQL / pgvector | Replaced by DynamoDB + BM25 + Redis (simpler, cheaper for FAQ scale) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-00 | Phase 0 | Complete (2026-03-01) |
| PLAT-00 | Phase 0 | Complete (2026-03-01) |
| VOIC-01 | Phase 0 | Complete (2026-03-01) |
| VOIC-02 | Phase 0 | Complete (2026-03-01) |
| VOIC-03 | Phase 1 | Pending |
| RAG-01 | Phase 1 | Pending |
| RAG-02 | Phase 1 | Pending |
| AGENT-01 | Phase 1.5 | Pending |
| AGENT-02 | Phase 1.5 | Pending |
| AGENT-03 | Phase 1.5 | Pending |
| AGENT-04 | Phase 1.5 (mock) → Phase 2.5 (real) | Pending |
| AGENT-05 | Phase 1.5 (mock) → Phase 5 (real) | Pending |
| OBS-04 | Phase 1.5 | Pending |
| PLAT-01 | Phase 2 | Pending |
| PLAT-02 | Phase 2 | Pending |
| PLAT-03 | Phase 2 | Pending |
| PLAT-04 | Phase 2 | Pending |
| API-01 | Phase 2 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 2 | Pending |
| API-04 | Phase 2 | Pending |
| VOIC-04 | Phase 2 | Pending |
| AGENT-06 | Phase 2 | Pending |
| OBS-06 | Phase 2.5 | Pending |
| OBS-07 | Phase 2.5 | Pending |
| OBS-01 | Phase 3 | Pending |
| OBS-02 | Phase 3 | Pending |
| OBS-05 | Phase 3 | Pending |
| RAG-04 | Phase 4 | Pending |
| OBS-03 | Phase 4 | Pending |
| RAG-03 | Phase 5 | Pending |
| REL-01 | Phase 7 | Pending |
| REL-02 | Phase 7 | Pending |
| REL-03 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 34 total (24 original + 10 new AGENT/OBS)
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-03-10 — added AGENT-01 through AGENT-06, OBS-04 through OBS-07, updated RAG-01/RAG-04, removed EC2/Aurora from scope*
