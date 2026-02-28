# Roadmap: Voice-Based Chatbot for Granicus PM

## Overview

Deliver this as a learning-first sequence: get a runnable MVP early, then add security/compliance hardening, then advanced reliability.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2): planned milestone work
- Decimal phases (1.1, 1.2): urgent insertions (marked with INSERTED)

- [ ] **Phase 0: Learning MVP Bootstrap** - Build the smallest runnable voice loop for self-learning
- [ ] **Phase 1: Runnable MVP Web Voice** - Make the MVP reliable enough to demo end-to-end
- [ ] **Phase 2: Security and Contracts Hardening** - Add the former Phase 0 security/compliance baseline
- [ ] **Phase 3: Observability and Production Readiness** - Add full dashboards, alarms, and test depth
- [ ] **Phase 4: RAG-Driven Agentic Reliability** - Retrieval, tools, supervision, and resilience hardening

## Phase Details

### Phase 0: Learning MVP Bootstrap
**Goal:** Get a simple browser-to-bot streaming path running quickly so the product is testable early.
**Depends on:** Nothing (first phase)
**Requirements:** [VOIC-01, VOIC-02]
**Gap Closure:** Addresses audit gaps for missing early runnable MVP flow
**Success Criteria** (what must be TRUE):
  1. Developer can start local services and complete one full voice turn.
  2. Browser streams mic audio and receives text/audio response through WS.
  3. Core adapter boundaries (ASR, LLM, TTS) exist with pluggable interfaces.
**Plans:** 3 plans

Plans:
- [ ] 00-01: Create minimal local stack and boot scripts for MVP run
- [ ] 00-02: Implement simple streaming ASR to LLM to TTS orchestrator flow
- [ ] 00-03: Wire browser widget to WS events for one-turn demo

### Phase 1: Runnable MVP Web Voice
**Goal:** Upgrade the learning slice into a stable demo path with guardrails and measurable latency targets.
**Depends on:** Phase 0
**Requirements:** [VOIC-03, VOIC-04]
**Gap Closure:** Closes audit gaps around stable E2E MVP flow before enterprise hardening
**Success Criteria** (what must be TRUE):
  1. MVP demo session can be run repeatedly without manual patching.
  2. Guardrails scrub/block unsafe output on the demo path.
  3. Phase-level latency checks exist for first partial/audio and turn timing.
**Plans:** 4 plans

Plans:
- [ ] 01-01: Improve session lifecycle and retry behavior for demo stability
- [ ] 01-02: Add content guardrails and safe-fail behaviors
- [ ] 01-03: Add latency probes and basic performance checks
- [ ] 01-04: Verify demo script and operator runbook

### Phase 2: Security and Contracts Hardening
**Goal:** Implement security/compliance baseline and interface governance that were previously in Phase 0.
**Depends on:** Phase 1
**Requirements:** [PLAT-01, PLAT-02, PLAT-03, PLAT-04, API-01, API-02, API-03, API-04, OBS-02]
**Gap Closure:** Closes audit gaps for security posture and contract completeness
**Success Criteria** (what must be TRUE):
  1. IAM, encryption, and private-network baseline is provisioned and validated.
  2. OpenAPI and WS schemas are versioned and verified against implementation.
  3. Threat model, authz matrix, and retention policy are documented and enforceable.
  4. Golden dataset with at least 50 curated conversations is available and versioned.
**Plans:** 4 plans

Plans:
- [ ] 02-01: Provision secure AWS baseline and secrets/config controls
- [ ] 02-02: Enforce CI security checks and quality gates
- [ ] 02-03: Finalize REST/WS contracts with strict error/auth scope rules
- [ ] 02-04: Build and store golden dataset assets with manifest

### Phase 3: Observability and Production Readiness
**Goal:** Add full telemetry, alarming, and contract/regression tests for dependable operation.
**Depends on:** Phase 2
**Requirements:** [OBS-01]
**Gap Closure:** Closes audit gaps for operational visibility and readiness
**Success Criteria** (what must be TRUE):
  1. Dashboards expose latency, reliability, safety, and cost signals end-to-end.
  2. Alerts exist for SLO misses and key dependency failures.
  3. Contract and regression tests run in CI and gate releases.
**Plans:** 3 plans

Plans:
- [ ] 03-01: Instrument traces and metrics across ASR/LLM/TTS and WS path
- [ ] 03-02: Configure CloudWatch/Grafana dashboards and actionable alarms
- [ ] 03-03: Add contract and golden replay regression automation

### Phase 4: RAG-Driven Agentic Reliability
**Goal:** Add production-grade retrieval/tooling supervision with reliability and cost controls.
**Depends on:** Phase 3
**Requirements:** [RAG-01, RAG-02, RAG-03, RAG-04, REL-01, REL-02, REL-03, OBS-03]
**Gap Closure:** Closes audit gaps for citation quality, supervised tooling, and resilience
**Success Criteria** (what must be TRUE):
  1. Document ingestion populates searchable/vector indexes and responses include citations.
  2. Tool plans and outputs are policy-reviewed by the supervisor before release.
  3. Replay and stress tests report quality, safety, latency, and resilience outcomes.
  4. Runtime resilience and budget guardrails mitigate dependency failures and cost spikes.
**Plans:** 4 plans

Plans:
- [ ] 04-01: Build ingest pipeline and OpenSearch indexing with metadata governance
- [ ] 04-02: Implement agentic tools and citation-aware response fusion
- [ ] 04-03: Add supervisor veto logic, policy checks, and security evaluations
- [ ] 04-04: Implement reliability controls, load testing, and cost guardrail automation

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Learning MVP Bootstrap | 0/3 | Not started | - |
| 1. Runnable MVP Web Voice | 0/4 | Not started | - |
| 2. Security and Contracts Hardening | 0/4 | Not started | - |
| 3. Observability and Production Readiness | 0/3 | Not started | - |
| 4. RAG-Driven Agentic Reliability | 0/4 | Not started | - |