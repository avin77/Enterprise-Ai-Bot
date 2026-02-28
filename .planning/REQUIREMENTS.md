# Requirements: Voice-Based Chatbot for Granicus PM

**Defined:** 2026-02-28
**Core Value:** Deliver fast, secure, and auditable voice conversations that agencies can trust in production.

## v1 Requirements

### Platform and Security

- [ ] **PLAT-01**: Platform provisions private networking, service endpoints, and encrypted storage in AWS us-east-1.
- [ ] **PLAT-02**: IAM roles enforce least privilege with explicit permission boundaries.
- [ ] **PLAT-03**: Security baseline includes threat model v1, authz matrix, and log retention policy.
- [ ] **PLAT-04**: CI enforces formatting, IaC/security scans, and dependency/SAST checks.

### Contracts and Interfaces

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
- [ ] **OBS-02**: Golden dataset of at least 50 curated conversations is stored with manifest and fixtures.
- [ ] **OBS-03**: Replay harness computes WER, intent match, citation quality, hallucination, and latency metrics.

### RAG and Agentic Reliability

- [ ] **RAG-01**: ETL pipeline ingests S3 documents into OpenSearch with required metadata fields.
- [ ] **RAG-02**: Retrieval-augmented responses include citations to source documents.
- [ ] **RAG-03**: Tooling supports property lookup and ticket recommendation through authenticated interfaces.
- [ ] **RAG-04**: Supervisor model can veto policy-violating tool plans and response content.

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
| Dedicated relational data layer in v1 | Current scope does not require RDS/DynamoDB complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VOIC-01 | Phase 0 | Pending |
| VOIC-02 | Phase 0 | Pending |
| VOIC-03 | Phase 1 | Pending |
| VOIC-04 | Phase 1 | Pending |
| PLAT-01 | Phase 2 | Pending |
| PLAT-02 | Phase 2 | Pending |
| PLAT-03 | Phase 2 | Pending |
| PLAT-04 | Phase 2 | Pending |
| API-01 | Phase 2 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 2 | Pending |
| API-04 | Phase 2 | Pending |
| OBS-02 | Phase 2 | Pending |
| OBS-01 | Phase 3 | Pending |
| RAG-01 | Phase 4 | Pending |
| RAG-02 | Phase 4 | Pending |
| RAG-03 | Phase 4 | Pending |
| RAG-04 | Phase 4 | Pending |
| REL-01 | Phase 4 | Pending |
| REL-02 | Phase 4 | Pending |
| REL-03 | Phase 4 | Pending |
| OBS-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after milestone gap planning update*