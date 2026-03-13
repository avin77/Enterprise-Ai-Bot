# Roadmap: Enterprise AI Voice Bot (GXA / Granicus)

## Overview

Incremental multi-agent voice bot for municipal government (Jackson County). Ships a RAG foundation first (Phase 1), then adds a full Claude-backed agent architecture — Orchestrator, Intent, Retrieval, Response, Memory, Tool, Supervisor agents — then hardens for public sector production with automated eval gates between major capability jumps.

**Design doc:** `docs/plans/2026-03-10-agentic-roadmap-design.md`

## Target Architecture

```
User Voice
   ↓
Speech To Text (AWS Transcribe)
   ↓
Orchestrator Agent (Claude — routes turn, classifies intent)
   ↓
 ┌──────────────────┬────────────────────┬──────────────────┐
 ▼                  ▼                    ▼
Intent Agent       Retrieval Agent       Tool Agent
(Claude+prompt)    (Claude+BM25+Dynamo)  (Claude+tools)
                        ↓
                  Response Agent
                  (Claude synthesis + citations)
                        ↓
                  Text to Speech (AWS Polly)
```

**Shared infra:** Memory Store (DynamoDB sessions) · Agent Trace Store · Intent Confusion Matrix · Eval Dashboard

## Deployment Tiers

Two-tier only (EC2 removed for simplicity):
- **Local:** Docker Compose — $0 compute, ~$5/mo API
- **ECS Fargate:** ap-south-1 cluster — ~$15-20/mo at 1024 MB / 512 CPU

## Phase Numbering

- Integer phases (0, 1, 2, ...): planned milestone work
- Decimal phases (1.5, 2.5): agentic capability insertions (INSERTED)
- Eval gate phases (3, 6): automated CI gates that block next phase if metrics fail

## Phase List

- [x] **Phase 0: Learning MVP Bootstrap** — Voice loop + ECS bootstrap (Complete 2026-03-01)
- [x] **Phase 1: GXA Voice Baseline** — RAG pipeline: DynamoDB + BM25 + Redis, 2-tier deploy, latency <1.5s (completed 2026-03-11)
- [ ] **Phase 1.5: Agentic Voice Core** ★ NEW — Orchestrator+Intent+Retrieval+Response agents, Mock Memory/Tool, agent traces
- [ ] **Phase 2: Public Sector Safety** — PII scrubbing, guardrails, Supervisor Agent, adversarial red team eval
- [ ] **Phase 2.5: Conversation Memory** ★ NEW — Real DynamoDB sessions, multi-turn history, conversation metrics, intent confusion matrix
- [ ] **Phase 3: Eval Gate I** — Automated CI gate (9 metrics) — BLOCKS Phase 4
- [ ] **Phase 4: RAG Scale + Citation Quality** — Hybrid BM25+embeddings, full county corpus, per-candidate scoring
- [ ] **Phase 5: Agentic Tools MVP** — Real Tool Agent: property lookup, utility, permits
- [ ] **Phase 6: Eval Gate II** — Full production readiness gate — BLOCKS Phase 7
- [ ] **Phase 7: Reliability + Cost Hardening** — Circuit breakers, spend caps, graceful degradation

---

## Phase Details

### Phase 0: Learning MVP Bootstrap ✓
**Goal:** Get a simple browser-to-bot streaming path running quickly and establish an initial AWS deployment path.
**Depends on:** Nothing
**Completed:** 2026-03-01
**Requirements:** [VOIC-01, VOIC-02, API-00, PLAT-00]
**Plans:** 5/5 complete

Plans:
- [x] 00-01-PLAN.md — Create layered backend skeleton with `/ws`, `/chat`, `/health` and MVP protections
- [x] 00-02-PLAN.md — Implement adapter-driven AWS orchestration with local mocks
- [x] 00-03-PLAN.md — Wire frontend streaming and text flows through backend-only APIs
- [x] 00-04-PLAN.md — Add containerized AWS bootstrap deployment path in us-east-1
- [x] 00-05-PLAN.md — Switch AWS bootstrap acceptance to CLI-first deploy/smoke/teardown flow

---

### Phase 1: GXA Voice Baseline
**Goal:** Runnable MVP voice bot with RAG knowledge base. Grounds Jackson County FAQ answers using DynamoDB + BM25 + Redis. Turn latency <1.5s end-to-end. 2-tier only (Local + ECS — EC2 removed).
**Depends on:** Phase 0
**Requirements:** [VOIC-03, RAG-01, RAG-02]
**Success Criteria** (what must be TRUE):
  1. Bot answers Jackson County FAQs correctly via RAG (DynamoDB + BM25 + Redis, all-MiniLM-L6-v2).
  2. RAGLLMAdapter injects top-3 FAQ context chunks into every LLM call with source attribution.
  3. Turn latency measured per-stage, below 1.5s p95 baseline.
  4. Same Docker Compose codebase runs locally and deploys to ECS without code changes (config only).
  5. ECS task uses 1024 MB memory (upgraded from 512 MB).
  6. IAM role includes: `dynamodb:Scan`, `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:PutItem`, `dynamodb:BatchWriteItem`, `dynamodb:UpdateItem`, `s3:GetObject`, `s3:ListBucket`, `cloudwatch:PutMetricData`.
  7. Redis failure falls back to direct BM25 — voice turn never fails due to Redis outage.
  8. Government synonym expansion applied to BM25 queries (≥30 synonym pairs for public sector terms).
**Plans:** 4/4 plans complete

Plans:
- [x] 01-01-PLAN.md — Local Docker Compose: all services, AWS creds, Phase 0 ASR/TTS integration, SLO <1.5s local
- [ ] 01-02-PLAN.md — RAG services: all-MiniLM embedding, BM25 reranker + Redis cache (with fallback), S3+DynamoDB ingest, synonym expansion
- [ ] 01-03-PLAN.md — ECS deploy: task definition (1024 MB), IAM role, RAGLLMAdapter wired to pipeline, load FAQs, E2E test
- [ ] 01-04-PLAN.md — Latency monitoring: CloudWatch per-stage metrics, conversation tracking (session_id, turns, duration), SLO baseline

**Eval Script:** `evals/phase-1-eval.py` (fixed seed, deterministic)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `latency_p95` | 95th pct ASR-start to TTS-complete, 100 test turns, fixed seed=42 | < 1.5s |
| `rag_recall` | Fraction of test queries with ≥1 relevant FAQ chunk in top-3 | > 75% |
| `deployment_success` | ECS task healthy after deploy, `/health` returns 200 | true |
| `redis_fallback_ok` | BM25 returns results when Redis killed during test | true |

---

### Phase 1.5: Agentic Voice Core ★ INSERTED
**Goal:** Add full Claude-backed multi-agent architecture on top of Phase 1 RAG. 3 real agents + 2 mock agents. Agent trace events emitted every turn. Intent confidence logging + fallback path.
**Depends on:** Phase 1
**Requirements:** [AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, OBS-04]
**Success Criteria** (what must be TRUE):
  1. Orchestrator+Intent Agent (single Claude haiku call) routes each turn and logs intent + confidence score.
  2. Retrieval Agent wraps Phase 1 BM25 RAG and returns top-3 chunks with source attribution.
  3. Response Agent (Claude sonnet) synthesizes grounded answer with citations.
  4. Mock Memory Store: `voicebot_sessions` DynamoDB table created with correct schema (PK: session_id, SK: turn_timestamp with hashed prefix); history not injected yet.
  5. Mock Tool Agent: interface defined, returns canned responses for supported intents.
  6. Agent trace event emitted every turn with: session_id, turn_id, intent, intent_confidence, routing_decision, retrieved_doc_ids, llm_prompt_tokens, llm_response_tokens, llm_latency_ms, tool_calls, total_latency_ms.
  7. Fallback path active: intent_confidence < 0.7 → skip Intent Agent → route directly to Retrieval Agent.
  8. Intent confusion matrix populated from every eval turn.
**Plans:** 4/5 plans executed

Plans:
- [x] 01.5-01-PLAN.md — Agent interfaces + Orchestrator+Intent Agent (Claude haiku, routing logic, confidence logging, fallback)
- [x] 01.5-02-PLAN.md — Retrieval Agent + Response Agent wired to Phase 1 RAG (completed 2026-03-11)
- [x] 01.5-03-PLAN.md — Mock Memory Store (DynamoDB schema + hashed prefix) + Mock Tool Agent (canned interface)
- [ ] 01.5-04-PLAN.md — Agent trace events: emit per turn, store in `voicebot_agent_traces`, intent confusion matrix to CloudWatch

**Eval Script:** `evals/phase-1.5-eval.py` (fixed seed, deterministic)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `routing_accuracy` | Fraction of turns where Orchestrator matched gold-label routing, 200 queries, seed=42 | > 90% |
| `grounded_response_rate` | Fraction of responses citing ≥1 source doc, automated citation check | > 85% |
| `trace_completeness` | Fraction of turns with all required trace fields present | 100% |
| `fallback_trigger_rate` | Low-confidence turns correctly routed to Retrieval fallback | 100% |

---

### Phase 2: Public Sector Safety
**Goal:** Implement security, safety guardrails, and adversarial red team validation for municipal resident interactions. Supervisor Agent with signed audit trail.
**Depends on:** Phase 1.5
**Requirements:** [PLAT-01, PLAT-02, API-01, AGENT-06]
**Success Criteria** (what must be TRUE):
  1. PII scrubber removes SSNs, phone numbers, and email addresses before logging or processing.
  2. Content guardrails prevent bot from giving legal or medical advice.
  3. Supervisor Agent vetoes unsafe tool plans and response content before delivery.
  4. Every veto produces a signed audit trail: session_id, turn_id, veto_reason, timestamp, supervisor_model_version.
  5. API contracts hardened for external-facing traffic (rate limits, auth scopes, error schemas).
  6. 200 adversarial red team queries: 100% handled safely (PII leakage, prompt injection, policy violations all blocked).
**Plans:** 4 plans

Plans:
- [ ] 02-01-PLAN.md — PII detection + scrubbing layer (pre-response, pre-log)
- [ ] 02-02-PLAN.md — Domain-specific content guardrails for public sector policy
- [ ] 02-03-PLAN.md — Supervisor Agent: Claude veto with signed audit trail; API schema hardening
- [ ] 02-04-PLAN.md — Adversarial red team eval suite (200 queries: PII + injection + policy)

**Eval Script:** `evals/phase-2-eval.py` (fixed seed, deterministic)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `pii_leak_rate` | Fraction of test outputs with detected PII patterns | 0% |
| `policy_violation_rate` | Fraction of guardrail test cases that bypassed guardrails | 0% |
| `adversarial_safe_rate` | Fraction of 200 red team queries handled safely | 100% |
| `audit_trail_completeness` | Fraction of vetoes with complete signed audit trail entry | 100% |

---

### Phase 2.5: Conversation Memory + Session Tracking ★ INSERTED
**Goal:** Replace Mock Memory Store with real DynamoDB session tables. Enable multi-turn conversations with 5-turn sliding context window. Populate all conversation metrics and per-intent confusion matrix.
**Depends on:** Phase 2
**Requirements:** [AGENT-04, OBS-06, OBS-07]
**Success Criteria** (what must be TRUE):
  1. `voicebot_sessions` DynamoDB table: PK = session_id, SK = turn_timestamp (hashed prefix to prevent hot partitions), TTL = 90 days.
  2. Orchestrator injects last 5 turns of history into context window every turn.
  3. All conversation metrics tracked per turn: session_id, turn_number, session_duration_ms, completion_status, follow_up_detected, fallback_triggered, clarification_requested.
  4. Per-intent precision/recall published to CloudWatch `IntentPrecision/{intent_name}` weekly.
  5. Cost per conversation tracked: compute_cost_usd + llm_cost_usd + storage_cost_usd.
  6. Cost alert fires if cost_per_turn > 2× baseline_expected_cost.
**Plans:** 3 plans

Plans:
- [ ] 02.5-01-PLAN.md — DynamoDB session table schema + TTL + hashed prefix hot partition prevention
- [ ] 02.5-02-PLAN.md — Multi-turn history injection (5-turn sliding window into Orchestrator)
- [ ] 02.5-03-PLAN.md — Conversation metrics pipeline: per-turn tracking, intent confusion matrix, cost breakdown + alerting

**Eval Script:** `evals/phase-2.5-eval.py` (fixed seed, deterministic)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `session_tracking_accuracy` | Fraction of test sessions where turn count + duration match expected | 100% |
| `multi_turn_coherence` | Fraction of 3-turn dialogues where response correctly references prior turn | > 85% |
| `cost_alert_fires` | Cost-per-turn alert triggers correctly when injected with 2× cost | true |
| `intent_confusion_matrix_populated` | Per-intent precision/recall visible in CloudWatch | true |

---

### Phase 3: Eval Gate I — Automated CI
**Goal:** Validate full voice + agent stack meets quality bar before scaling RAG or adding real tools. Automated gate that BLOCKS Phase 4 execution.
**Depends on:** Phase 2.5
**Requirements:** [OBS-01, OBS-02, OBS-05]
**Success Criteria** (what must be TRUE):
  1. `evals/phase-3-eval.py` runs with fixed seed=42, publishes to CloudWatch, returns exit code 0 if ALL metrics pass.
  2. Eval dashboard `voice-bot-mvp-evals` has: pass/fail badge per run, filter by date + last 2h, sortable metric table columns.
  3. CI pipeline blocks Phase 4 plan execution if gate returns exit code 1.
  4. All 9 gate metrics meet targets simultaneously.
**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Gold FAQ eval dataset: 50 curated queries with gold-label routing, source, expected answer
- [ ] 03-02-PLAN.md — Automated eval suite runner + CloudWatch dashboard with filters/sort/pass-fail

**Gate Metrics (ALL must pass simultaneously):**
| Metric | Definition | Target |
|--------|-----------|--------|
| `latency_p95` | 95th pct turn latency, 200 turns, seed=42 | < 2s |
| `rag_recall` | Fraction of queries with ≥1 relevant chunk in top-3 | > 75% |
| `routing_accuracy` | Orchestrator matches gold-label routing, 200 queries | > 90% |
| `grounded_response_rate` | Responses citing ≥1 source doc | > 85% |
| `task_completion_rate` | Simulated sessions marked complete, 50 sessions | > 80% |
| `hallucination_rate` | Claims not supported by retrieved chunks (heuristic proxy) | < 5% |
| `pii_leak_rate` | Test outputs containing detected PII patterns | 0% |
| `adversarial_safe_rate` | Red team queries handled safely | 100% |
| `cost_per_turn_usd` | Average compute + LLM + storage per turn | < $0.03 |

---

### Phase 4: RAG Scale + Citation Quality
**Goal:** Expand knowledge corpus beyond FAQs to full county documents. Add hybrid BM25+embedding re-ranking with per-candidate score logging.
**Depends on:** Phase 3 (gate must pass — Phase 4 is BLOCKED until Gate I passes)
**Requirements:** [RAG-01, RAG-02]
**Success Criteria** (what must be TRUE):
  1. Corpus expanded to ≥20 county documents beyond the FAQ sheet.
  2. Hybrid retrieval: BM25 initial candidates → re-ranked by embedding similarity (embeddings already stored in DynamoDB from Phase 1).
  3. Per-candidate BM25 score + embedding score logged every retrieval (for error analysis).
  4. Query expansion paraphrase tests pass for public sector synonyms.
  5. Citations include source document + page/section reference.
**Plans:** 3 plans

Plans:
- [ ] 04-01-PLAN.md — Document corpus expansion: S3 ingestion pipeline for county PDFs, chunking strategy
- [ ] 04-02-PLAN.md — Hybrid retrieval: embedding re-ranker on BM25 candidates, per-candidate score logging
- [ ] 04-03-PLAN.md — Citation quality: page/section attribution, citation precision eval, paraphrase tests

**Eval Script:** `evals/phase-4-eval.py` (fixed seed)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `corpus_coverage` | Fraction of known county FAQ topics with ≥1 relevant chunk | > 90% |
| `citation_precision` | Fraction of cited sources actually relevant to answer | > 85% |
| `hybrid_recall_gain` | Hybrid recall vs BM25-only on same test set | > 5% improvement |

---

### Phase 5: Agentic Tools MVP
**Goal:** Replace Mock Tool Agent with real municipal tool integrations. Tool calls logged in agent traces. Supervisor vetoes unsafe plans.
**Depends on:** Phase 4
**Requirements:** [RAG-03, AGENT-05]
**Success Criteria** (what must be TRUE):
  1. Tool Agent executes ≥3 real municipal tools (property lookup, utility status, permit status).
  2. Tool calls logged in agent trace events with tool_name, inputs, output, latency_ms.
  3. Supervisor Agent vetoes unsafe tool plans before execution; audit trail entry created.
**Plans:** 3 plans

Plans:
- [ ] 05-01-PLAN.md — Tool Agent: Claude+tools interface, tool routing, Supervisor integration
- [ ] 05-02-PLAN.md — Municipal tool integrations (property lookup, utility, permit)
- [ ] 05-03-PLAN.md — Tool safety eval + audit trail verification

**Eval Script:** `evals/phase-5-eval.py` (fixed seed)
**Key Metrics:**
| Metric | Definition | Target |
|--------|-----------|--------|
| `tool_success_rate` | Fraction of tool calls completing without error | > 85% |
| `tool_latency_p95` | 95th pct tool call latency | < 2s |
| `tool_veto_accuracy` | Fraction of unsafe tool plans correctly vetoed by Supervisor | 100% |

---

### Phase 6: Eval Gate II — Full Production Readiness
**Goal:** Full production readiness gate. BLOCKS Phase 7.
**Depends on:** Phase 5
**Requirements:** [OBS-01, OBS-02, OBS-05, REL-01]
**Success Criteria** (what must be TRUE):
  1. All Phase 3 gate metrics still pass.
  2. Load test: 50 concurrent turns complete within SLO without errors.
  3. Security scan: no critical findings.
  4. Cost per turn confirmed < $0.03 under load.
**Plans:** 2 plans

Plans:
- [ ] 06-01-PLAN.md — Load testing (50 concurrent turns) + security scan automation
- [ ] 06-02-PLAN.md — Consolidated eval gate runner with all metrics + dashboard

**Gate Metrics:** All Phase 3 metrics + `concurrent_turns_ok: true` + `security_scan_critical: 0`.

---

### Phase 7: Reliability + Cost Hardening
**Goal:** Production resilience: circuit breakers, spend caps, graceful text-only fallback.
**Depends on:** Phase 6 (gate must pass)
**Requirements:** [REL-01, REL-02, REL-03]
**Success Criteria** (what must be TRUE):
  1. Circuit breakers prevent cascade failures from Redis/DynamoDB outages.
  2. Bot falls back to text-only mode if TTS fails (REL-02).
  3. Per-session cost cap enforced; alert fires at 2× expected cost.
  4. 99.5% uptime verified under simulated load.
**Plans:** 3 plans

Plans:
- [ ] 07-01-PLAN.md — Circuit breakers + graceful degradation (text fallback)
- [ ] 07-02-PLAN.md — Spend caps + cost alerting
- [ ] 07-03-PLAN.md — Reliability eval: uptime verification, failure injection tests

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Learning MVP Bootstrap | 5/5 | Complete | 2026-03-01 |
| 1. GXA Voice Baseline | 4/4 | Complete   | 2026-03-11 |
| 1.5. Agentic Voice Core ★ | 4/5 | In Progress|  |
| 2. Public Sector Safety | 0/4 | Not started | - |
| 2.5. Conversation Memory ★ | 0/3 | Not started | - |
| 3. Eval Gate I (Automated CI) | 0/2 | Not started | - |
| 4. RAG Scale + Citation Quality | 0/3 | Not started | - |
| 5. Agentic Tools MVP | 0/3 | Not started | - |
| 6. Eval Gate II (Automated CI) | 0/2 | Not started | - |
| 7. Reliability + Cost Hardening | 0/3 | Not started | - |

**Total:** 10 phases · 31 plans remaining · ★ = new phase inserted 2026-03-10
