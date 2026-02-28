# Roadmap: Voice-Based Chatbot for Granicus PM

## Overview

Deliver a government-ready web voice chatbot in three phases: secure foundations, end-to-end streaming MVP, and RAG-driven agentic reliability.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2): planned milestone work
- Decimal phases (1.1, 1.2): urgent insertions (marked with INSERTED)

- [ ] **Phase 0: Foundations and Golden Dataset** - Security baseline, contracts, and evaluation seed assets
- [ ] **Phase 1: MVP Web Voice** - Authenticated streaming voice loop and operational dashboards
- [ ] **Phase 2: RAG-Driven Agentic Reliability** - Retrieval, tools, supervision, and resilience hardening

## Phase Details

### Phase 0: Foundations and Golden Dataset
**Goal**: Establish the secure cloud baseline, API/WS contracts, and golden dataset needed for all subsequent implementation.
**Depends on**: Nothing (first phase)
**Requirements**: [PLAT-01, PLAT-02, PLAT-03, PLAT-04, API-01, API-02, API-03, API-04, OBS-02]
**Success Criteria** (what must be TRUE):
  1. Infrastructure baseline and CI security gates are provisioned and validated.
  2. OpenAPI and WS schemas are versioned and reviewed for compatibility rules.
  3. Threat model, authz matrix, and logging policy are documented and enforceable.
  4. Golden dataset with at least 50 conversations is stored with manifest and fixtures.
**Plans**: 3 plans

Plans:
- [ ] 00-01: Provision AWS baseline infrastructure, IAM/KMS, and storage components
- [ ] 00-02: Set up CI security pipeline and local development environment with mocks
- [ ] 00-03: Define contracts, security artifacts, and golden dataset assets

### Phase 1: MVP Web Voice
**Goal**: Deliver an authenticated browser voice experience with streaming transcript/audio and measurable SLO telemetry.
**Depends on**: Phase 0
**Requirements**: [VOIC-01, VOIC-02, VOIC-03, VOIC-04, OBS-01]
**Success Criteria** (what must be TRUE):
  1. Users can open authenticated sessions and stream microphone audio over WS.
  2. Users receive partial transcript updates and streamed bot audio during each turn.
  3. Guardrails prevent unsafe output and latency dashboards report core SLOs.
**Plans**: 4 plans

Plans:
- [ ] 01-01: Build web voice widget with streaming protocol support and JWT integration
- [ ] 01-02: Implement orchestrator streaming ASR to LLM to TTS pipeline
- [ ] 01-03: Add guardrails, prompt caching, and basic FAQ retrieval integration
- [ ] 01-04: Configure tracing, metrics, alarms, and contract test coverage

### Phase 2: RAG-Driven Agentic Reliability
**Goal**: Add production-grade retrieval/tooling supervision with reliability and cost controls.
**Depends on**: Phase 1
**Requirements**: [RAG-01, RAG-02, RAG-03, RAG-04, REL-01, REL-02, REL-03, OBS-03]
**Success Criteria** (what must be TRUE):
  1. Document ingestion populates searchable/vector indexes and responses include citations.
  2. Tool plans and outputs are policy-reviewed by the supervisor before release.
  3. Replay and stress tests report quality, safety, latency, and resilience outcomes.
  4. Runtime resilience and budget guardrails mitigate dependency failures and cost spikes.
**Plans**: 4 plans

Plans:
- [ ] 02-01: Build ingest pipeline and OpenSearch indexing with metadata governance
- [ ] 02-02: Implement agentic tools and citation-aware response fusion
- [ ] 02-03: Add supervisor veto logic, policy checks, and security evaluations
- [ ] 02-04: Implement reliability controls, load testing, and cost guardrail automation

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Foundations and Golden Dataset | 0/3 | Not started | - |
| 1. MVP Web Voice | 0/4 | Not started | - |
| 2. RAG-Driven Agentic Reliability | 0/4 | Not started | - |
