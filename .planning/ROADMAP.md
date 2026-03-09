# Roadmap: Voice-Based Chatbot for TPM

## Overview

Use an AI product management sequence: ship a learning MVP quickly, harden security, run explicit evaluation gates between major capability jumps, then split RAG and agentic maturity into separate phases.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, ...): planned milestone work
- Decimal phases (2.1, 2.2): urgent insertions (marked with INSERTED)

- [x] **Phase 0: Learning MVP Bootstrap** - Build the smallest runnable voice loop for self-learning (Completed 2026-03-01)
- [ ] **Phase 1: GXA Voice Baseline** - Implement VAD tuning and RAG-lite for Johnson County FAQs
- [ ] **Phase 2: Public Sector Safety** - Implement guardrails, PII scrubbing, and policy enforcement
- [ ] **Phase 3: Eval Gate I (Resident UX)** - Validate accuracy and latency against human benchmarks
- [ ] **Phase 4: RAG Scale and Citation Quality** - Expand knowledge corpus and deliver grounded citations
- [ ] **Phase 5: Agentic Tools Enablement** - Add municipal tool execution (e.g., property lookup)
- [ ] **Phase 6: Eval Gate II (Task Completion)** - Evaluate tool-calling effectiveness and safety
- [ ] **Phase 7: Reliability and Cost Hardening** - Add resilience, failover, and spend controls

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
**Plans:** 5 plans

Plans:
- [x] 00-01-PLAN.md - Create layered backend skeleton with `/ws`, `/chat`, `/health` and MVP protections
- [x] 00-02-PLAN.md - Implement adapter-driven AWS orchestration with local mocks
- [x] 00-03-PLAN.md - Wire frontend streaming and text flows through backend-only APIs
- [x] 00-04-PLAN.md - Add containerized AWS bootstrap deployment path in us-east-1
- [x] 00-05-PLAN.md - Switch AWS bootstrap acceptance to CLI-first deploy/smoke/teardown flow

### Phase 1: GXA Voice Baseline
**Goal:** Transition the MVP into an authoritative public sector agent with tuned voice activity and local knowledge.
**Depends on:** Phase 0
**Requirements:** [VOIC-03, RAG-01, RAG-02]
**Gap Closure:** Accelerates knowledge grounding and voice usability for resident-facing demos.
**Success Criteria** (what must be TRUE):
  1. Bot answers Jackson County FAQs correctly from a RAG index backed by Aurora PostgreSQL + pgvector.
  2. VoicePipeline injects top-3 to top-5 FAQ context chunks into every LLM call with source attribution.
  3. Turn latency (ASR start to TTS complete) is measured per-stage and below 2.5s baseline.
**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md - Define KnowledgeAdapter contract, wire RAG stage into VoicePipeline, add per-stage timing fields
- [ ] 01-02-PLAN.md - Implement AwsKnowledgeAdapter with Aurora pgvector hybrid search and PDF ingest pipeline
- [ ] 01-03-PLAN.md - Add CloudWatch latency metrics, /metrics endpoint, and human checkpoint for SLO baseline

### Phase 2: Public Sector Safety
**Goal:** Implement security and safety guardrails required for municipal resident interactions.
**Depends on:** Phase 1
**Requirements:** [PLAT-01, PLAT-02, API-01]
**Gap Closure:** Addresses public sector risk around PII and legal liability.
**Success Criteria** (what must be TRUE):
  1. PII scrubber removes SSNs or phone numbers before logging/processing.
  2. Content guardrails prevent the bot from giving legal or medical advice.
  3. API contracts are hardened for external-facing traffic.
**Plans:** 3 plans

Plans:
- [ ] 02-01: Implement PII detection and scrubbing layer
- [ ] 02-02: Add domain-specific guardrails for public sector policy
- [ ] 02-03: Harden API schemas and rate limits for public traffic

### Phase 3: Eval Gate I (Resident UX)
**Goal:** Validate readiness of the voice loop and knowledge quality before scaling RAG.
**Depends on:** Phase 2
**Requirements:** [OBS-01, OBS-02]
**Gap Closure:** Ensures resident-facing quality bar is met before deeper investment.
**Success Criteria** (what must be TRUE):
  1. Task completion rate for FAQ queries is > 85%.
  2. Accuracy check (grounding) shows zero hallucinations on "Gold" FAQ set.
**Plans:** 2 plans

Plans:
- [ ] 03-01: Build "Gold" FAQ evaluation dataset for Johnson County
- [ ] 03-02: Run baseline Resident UX audit and sign off for Phase 4

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Learning MVP Bootstrap | 5/5 | Complete | 2026-03-05 |
| 1. GXA Voice Baseline | 0/3 | In progress | - |
| 2. Public Sector Safety | 0/3 | Not started | - |
| 3. Eval Gate I (Resident UX) | 0/2 | Not started | - |
| 4. RAG Scale and Citation Quality | 0/3 | Not started | - |
| 5. Agentic Tools Enablement | 0/3 | Not started | - |
| 6. Eval Gate II (Task Completion) | 0/2 | Not started | - |
| 7. Reliability and Cost Hardening | 0/3 | Not started | - |
