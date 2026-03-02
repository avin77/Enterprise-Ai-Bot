# Roadmap: Voice-Based Chatbot for TPM

## Overview

Use an AI product management sequence: ship a learning MVP quickly, harden security, run explicit evaluation gates between major capability jumps, then split RAG and agentic maturity into separate phases.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, ...): planned milestone work
- Decimal phases (2.1, 2.2): urgent insertions (marked with INSERTED)

- [x] **Phase 0: Learning MVP Bootstrap** - Build the smallest runnable voice loop for self-learning (Completed 2026-03-01)
- [ ] **Phase 1: Runnable MVP Web Voice** - Stabilize MVP turn quality and safety behavior
- [ ] **Phase 2: Security and Contracts Hardening** - Implement baseline security posture and contract governance
- [ ] **Phase 3: Eval Gate I (MVP + Security)** - Validate MVP plus security baseline before RAG investment
- [ ] **Phase 4: RAG Data Ingestion Foundation** - Build ingest pipeline and searchable corpus
- [ ] **Phase 5: RAG Retrieval and Citation Quality** - Deliver grounded responses with citation correctness
- [ ] **Phase 6: Eval Gate II (RAG Quality)** - Evaluate grounding, hallucination, and retrieval effectiveness
- [ ] **Phase 7: Agentic Tools Enablement** - Add tool execution capabilities behind controlled interfaces
- [ ] **Phase 8: Agentic Safety and Supervisor Controls** - Enforce policy checks and supervisor veto flow
- [ ] **Phase 9: Reliability and Cost Hardening** - Add resilience, failover behavior, and spend controls

## Phase Details

### Phase 0: Learning MVP Bootstrap
**Goal:** Get a simple browser-to-bot streaming path running quickly and establish an initial AWS deployment path in us-east-1.
**Depends on:** Nothing (first phase)
**Requirements:** [VOIC-01, VOIC-02, API-00, PLAT-00]
**Gap Closure:** Addresses audit gaps for missing early runnable MVP flow
**Success Criteria** (what must be TRUE):
  1. Developer can start local services and complete one full voice turn.
  2. Frontend streams through backend endpoints (`/ws`, `/chat`, `/health`) and never calls AWS directly.
  3. Backend performs minimal token validation and rate limiting for MVP API protection.
  4. Core adapter boundaries (ASR, LLM, TTS) use AWS-backed implementations with local mocks.
  5. Backend service is deployable to an AWS dev environment in us-east-1 for MVP validation.
**Plans:** 4 plans

Plans:
- [x] 00-01-PLAN.md - Create layered backend skeleton with `/ws`, `/chat`, `/health` and MVP protections
- [x] 00-02-PLAN.md - Implement adapter-driven AWS orchestration with local mocks
- [x] 00-03-PLAN.md - Wire frontend streaming and text flows through backend-only APIs
- [x] 00-04-PLAN.md - Add containerized AWS bootstrap deployment path in us-east-1

### Phase 1: Runnable MVP Web Voice
**Goal:** Upgrade the learning slice into a stable demo path with guardrails and measurable latency targets.
**Depends on:** Phase 0
**Requirements:** [VOIC-03, VOIC-04]
**Gap Closure:** Closes audit gaps around stable E2E MVP flow before enterprise hardening
**Success Criteria** (what must be TRUE):
  1. MVP demo session can be run repeatedly without manual patching.
  2. Guardrails scrub or block unsafe output on the demo path.
  3. Phase-level latency checks exist for first partial/audio and turn timing.
**Plans:** 4 plans

Plans:
- [ ] 01-01: Improve session lifecycle and retry behavior for demo stability
- [ ] 01-02: Add content guardrails and safe-fail behaviors
- [ ] 01-03: Add latency probes and basic performance checks
- [ ] 01-04: Verify demo script and operator runbook

### Phase 2: Security and Contracts Hardening
**Goal:** Implement security/compliance baseline and interface governance before advanced capability expansion.
**Depends on:** Phase 1
**Requirements:** [PLAT-01, PLAT-02, PLAT-03, PLAT-04, API-01, API-02, API-03, API-04]
**Gap Closure:** Closes audit gaps for security posture and contract completeness
**Success Criteria** (what must be TRUE):
  1. IAM, encryption, and private-network baseline is provisioned and validated.
  2. OpenAPI and WS schemas are versioned and verified against implementation.
  3. Threat model, authz matrix, and retention policy are documented and enforceable.
  4. CI security checks are active and gating changes.
**Plans:** 4 plans

Plans:
- [ ] 02-01: Provision secure AWS baseline and secrets/config controls
- [ ] 02-02: Enforce CI security checks and quality gates
- [ ] 02-03: Finalize REST/WS contracts with strict error/auth scope rules
- [ ] 02-04: Validate auth scope mapping and policy enforcement path

### Phase 3: Eval Gate I (MVP + Security)
**Goal:** Validate readiness after MVP + security before investing in retrieval and tooling complexity.
**Depends on:** Phase 2
**Requirements:** [OBS-01, OBS-02]
**Gap Closure:** Adds in-between evaluation gate to reduce downstream rework risk
**Success Criteria** (what must be TRUE):
  1. Dashboards expose latency, reliability, safety, and cost baselines.
  2. Golden dataset of at least 50 curated conversations is stored and versioned.
  3. Go/no-go criteria for RAG phase are documented with measured baseline values.
**Plans:** 3 plans

Plans:
- [ ] 03-01: Instrument traces and core metrics across ASR/LLM/TTS and WS path
- [ ] 03-02: Build and version golden dataset assets and manifests
- [ ] 03-03: Run baseline evaluation and publish gate decision notes

### Phase 4: RAG Data Ingestion Foundation
**Goal:** Build ingestion pipeline and indexing layer that powers retrieval.
**Depends on:** Phase 3
**Requirements:** [RAG-01]
**Gap Closure:** Splits RAG foundation from downstream retrieval quality and agentic work
**Success Criteria** (what must be TRUE):
  1. Documents ingest from S3 through ETL into OpenSearch with required metadata.
  2. Indexing is repeatable and auditable with clear data lineage.
**Plans:** 3 plans

Plans:
- [ ] 04-01: Build ETL pipeline from S3 source to processed chunks
- [ ] 04-02: Configure OpenSearch schema and indexing jobs
- [ ] 04-03: Validate indexing quality and metadata coverage

### Phase 5: RAG Retrieval and Citation Quality
**Goal:** Deliver grounded retrieval responses with accurate and useful citations.
**Depends on:** Phase 4
**Requirements:** [RAG-02]
**Gap Closure:** Separates retrieval quality from data plumbing and agentic scope
**Success Criteria** (what must be TRUE):
  1. Responses include citations linked to retrieved sources.
  2. Retrieval behavior is tunable with measurable relevance improvements.
**Plans:** 3 plans

Plans:
- [ ] 05-01: Implement retrieval orchestration and context construction
- [ ] 05-02: Add citation formatting and source linking in responses
- [ ] 05-03: Tune retrieval parameters using benchmark queries

### Phase 6: Eval Gate II (RAG Quality)
**Goal:** Evaluate grounding quality before adding tool-calling complexity.
**Depends on:** Phase 5
**Requirements:** [OBS-03]
**Gap Closure:** Adds second in-between evaluation gate to prevent compounding quality issues
**Success Criteria** (what must be TRUE):
  1. Replay harness reports WER, intent match, citation quality, hallucination, and latency.
  2. RAG quality threshold is met for progression to agentic tooling.
**Plans:** 2 plans

Plans:
- [ ] 06-01: Implement replay harness automation and score reporting
- [ ] 06-02: Execute evaluation suite and document gate decision

### Phase 7: Agentic Tools Enablement
**Goal:** Add core business tools with safe execution interfaces.
**Depends on:** Phase 6
**Requirements:** [RAG-03]
**Gap Closure:** Splits tool integration from supervision/policy governance for cleaner delivery
**Success Criteria** (what must be TRUE):
  1. Property lookup and ticket recommendation tools execute through defined interfaces.
  2. Tool outputs are integrated into responses with traceable provenance.
**Plans:** 3 plans

Plans:
- [ ] 07-01: Implement tool contracts and adapters for property lookup
- [ ] 07-02: Implement ticket recommendation workflow integration
- [ ] 07-03: Add tool execution telemetry and error handling

### Phase 8: Agentic Safety and Supervisor Controls
**Goal:** Enforce policy checks and supervisor controls for tool and response safety.
**Depends on:** Phase 7
**Requirements:** [RAG-04]
**Gap Closure:** Isolates safety governance from initial tool delivery risk
**Success Criteria** (what must be TRUE):
  1. Supervisor can veto policy-violating tool calls/responses.
  2. Policy decisions are logged with auditable evidence.
**Plans:** 3 plans

Plans:
- [ ] 08-01: Implement supervisor review pipeline for tool plans
- [ ] 08-02: Add policy evaluation hooks before output release
- [ ] 08-03: Validate jailbreak and unsafe-tool scenarios

### Phase 9: Reliability and Cost Hardening
**Goal:** Improve production resilience and enforce operational spend controls.
**Depends on:** Phase 8
**Requirements:** [REL-01, REL-02, REL-03]
**Gap Closure:** Closes resilience/cost gaps after functional and safety maturity
**Success Criteria** (what must be TRUE):
  1. Runtime uses bounded retries/backoff and circuit breakers.
  2. Service can fall back to text-only mode when speech components degrade.
  3. Budget thresholds and per-session caps trigger protective actions.
**Plans:** 3 plans

Plans:
- [ ] 09-01: Implement circuit breakers and retry policy controls
- [ ] 09-02: Implement graceful text-only fallback mode
- [ ] 09-03: Add budget guardrail automation and alerting

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Learning MVP Bootstrap | 4/4 | Complete | 2026-03-01 |
| 1. Runnable MVP Web Voice | 0/4 | Not started | - |
| 2. Security and Contracts Hardening | 0/4 | Not started | - |
| 3. Eval Gate I (MVP + Security) | 0/3 | Not started | - |
| 4. RAG Data Ingestion Foundation | 0/3 | Not started | - |
| 5. RAG Retrieval and Citation Quality | 0/3 | Not started | - |
| 6. Eval Gate II (RAG Quality) | 0/2 | Not started | - |
| 7. Agentic Tools Enablement | 0/3 | Not started | - |
| 8. Agentic Safety and Supervisor Controls | 0/3 | Not started | - |
| 9. Reliability and Cost Hardening | 0/3 | Not started | - |
