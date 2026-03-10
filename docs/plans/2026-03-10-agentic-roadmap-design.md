# Design: Agentic Voice Bot Roadmap

**Date:** 2026-03-10
**Author:** Claude Code + TPM session
**Status:** Approved

---

## Problem Statement

The original roadmap was a simple RAG pipeline (ASR → LLM → TTS) with no agent architecture. The system cannot route different query types to specialized handlers, cannot maintain conversation memory, cannot execute municipal tools, and has no formal eval gates to block bad deploys. This design adds a full multi-agent architecture incrementally on top of the existing codebase, without disrupting completed Phase 0 work.

---

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

**Shared Infrastructure:**
- Memory Store (DynamoDB: session_id PK, turn_timestamp SK, TTL 90 days)
- Agent Trace Store (DynamoDB or CloudWatch Logs Insights: per-turn observability)
- Intent Confusion Matrix (logged per turn, aggregated in CloudWatch)
- Eval Dashboard (CloudWatch + DynamoDB `voicebot_evals` table)

---

## Roadmap Structure

Option C (Incremental Upgrade) selected. Existing 8 phases preserved. Two new decimal phases inserted.

### Phase 0 ✓ Learning MVP Bootstrap (Complete)
Nothing changes. Voice loop + ECS deploy working.

### Phase 1: GXA Voice Baseline (Updated)
**Change:** Remove EC2 from scope. 2-tier only: Local Docker + ECS Fargate.
Stack: DynamoDB + BM25 + Redis, all-MiniLM-L6-v2 embeddings.
No agent routing yet — direct RAG pipeline.

### Phase 1.5 ★ NEW: Agentic Voice Core
Add multi-agent architecture on top of Phase 1 RAG:
- Orchestrator+Intent Agent (single Claude call: routes + classifies)
- Retrieval Agent (Claude wraps BM25 RAG from Phase 1)
- Response Agent (Claude synthesizes grounded answer + citations)
- Mock Memory Store (DynamoDB schema created, history not used yet)
- Mock Tool Agent (interface defined, canned responses only)

Intent infrastructure:
- Intent confidence logged every turn
- Fallback path if confidence < threshold (escalate to Retrieval Agent directly)
- Intent confusion matrix built from the start

Agent trace events emitted every turn:
```json
{
  "session_id": "...",
  "turn_id": "...",
  "intent": "property_tax_lookup",
  "intent_confidence": 0.92,
  "routing_decision": "retrieval_agent",
  "retrieved_doc_ids": ["faq-042", "faq-091"],
  "llm_prompt_tokens": 412,
  "llm_response_tokens": 87,
  "llm_latency_ms": 780,
  "tool_calls": [],
  "total_latency_ms": 1240
}
```

### Phase 2: Public Sector Safety (Upgraded)
Original scope preserved. Additions:
- Supervisor Agent (Claude vetoes unsafe plans/responses)
- Signed audit trail: every veto logged with decision reason + timestamp
- **Adversarial red team eval: 200 queries** targeting PII leakage, prompt injection, policy violations
- Eval gate passes ONLY if 100% of adversarial tests are handled safely

### Phase 2.5 ★ NEW: Conversation Memory + Session Tracking
Replace Mock Memory Store with real implementation:
- DynamoDB table: `voicebot_sessions` (PK: session_id, SK: turn_timestamp — hashed prefix to avoid hot partitions)
- Multi-turn history injected into Orchestrator context window
- Session metrics tracked: turns, duration, completion, follow-up rate, clarification rate
- Per-intent precision/recall confusion matrix populated from real data

### Phase 3: Eval Gate I — UPGRADED to Automated CI
Original scope (Gold FAQ evaluation) upgraded to automated CI gate:
- `evals/phase-3-eval.py` with fixed random seed for deterministic runs
- Runs on every PR targeting `main`
- Publishes to `voicebot/evals` CloudWatch namespace
- Dashboard: pass/fail per run, filterable by: day ran, last 2 hours, sort by metric
- Blocks Phase 4 execution if gate fails

**Gate Metrics:**

| Metric | Definition | Target |
|--------|-----------|--------|
| `latency_p95` | 95th percentile of ASR-start to TTS-complete, over 200 test turns | < 2s |
| `rag_recall` | Fraction of test queries where ≥1 relevant FAQ chunk in top-3 results | > 75% |
| `routing_accuracy` | Fraction of turns where Orchestrator matched human gold-label routing, over 200 queries | > 90% |
| `grounded_response_rate` | Fraction of responses citing ≥1 source document, verified by automated citation check | > 85% |
| `task_completion_rate` | Fraction of simulated conversations marked complete (not abandoned), over 50 sessions | > 80% |
| `hallucination_rate` | Fraction of answers containing claims not supported by retrieved chunks (heuristic proxy) | < 5% |
| `pii_leak_rate` | Fraction of test outputs containing detected PII patterns | 0% |
| `adversarial_safe_rate` | Fraction of 200 red team queries handled without policy violation | 100% |
| `cost_per_turn` | Average compute + LLM inference + storage cost per voice turn | < $0.03 |

### Phase 4: RAG Scale + Citation Quality (Upgraded)
Original scope + hybrid retrieval:
- Expand corpus from FAQs to full county documents
- Hybrid retrieval: BM25 initial candidate set → re-rank with embedding similarity
- Per-candidate scores logged for analysis (which stage caused errors)
- Query expansion paraphrase tests for public sector language
- DynamoDB stores metadata; embeddings stay as binary blobs for re-ranking

### Phase 5: Agentic Tools MVP
Replace Mock Tool Agent with real municipal integrations:
- Property lookup (county assessor API)
- Utility payment status
- Permit status
- Tool calls logged in agent trace events

### Phase 6: Eval Gate II — UPGRADED to Automated CI
Full production readiness gate. Same pattern as Phase 3.
Additional checks: load test (50 concurrent turns), cost per turn, security scan.

### Phase 7: Reliability + Cost Hardening
Circuit breakers, graceful degradation (text fallback if voice fails), spend caps.
Early alert if cost per turn > 2x expected value.

---

## Eval Infrastructure (Cross-Cutting)

### Eval Script Template
Every `evals/phase-N-eval.py`:
1. Seeds randomization with fixed seed (reproducible results)
2. Loads test dataset from `evals/fixtures/phase-N-queries.json`
3. Runs queries against live or mock endpoints
4. Computes all metrics with explicit definitions
5. Publishes to CloudWatch `voicebot/evals` namespace
6. Writes result row to DynamoDB `voicebot_evals` table
7. Returns exit code 0 (all pass) or 1 (any fail)

### Eval Dashboard Spec
CloudWatch dashboard `voice-bot-mvp-evals`:
- **Filter widgets:** Date picker, Time range (last 2h, last 24h, last 7d)
- **Columns per run:** phase, run_timestamp, pass/fail, metric values
- **Sort:** by timestamp (default), by metric (clickable header)
- **Alarms:** trigger if gate fails on `main` branch

### Agent Trace Store
- Table: `voicebot_agent_traces`
- PK: `session_id#turn_id` (composite)
- SK: `timestamp`
- TTL: 90 days
- Queryable via CloudWatch Logs Insights or direct DynamoDB scan
- Shown in TPM dashboard under "Agent Routing" tab

### Intent Confusion Matrix
- Logged per turn: `predicted_intent`, `confidence`, `gold_label` (from eval fixtures)
- Aggregated weekly in CloudWatch metric `IntentPrecision/{intent_name}`
- Fallback path: if `confidence < 0.7` → skip Intent Agent → go directly to Retrieval Agent

### Cost Modeling
Track per conversation:
- `compute_cost_usd`: ECS task hours × Fargate price per hour
- `llm_cost_usd`: (prompt_tokens + completion_tokens) × Bedrock price per token
- `storage_cost_usd`: DynamoDB RCU/WCU + S3 GET requests
- Alert: `TotalCostPerTurn > 2 × baseline_expected_cost`

---

## Infrastructure Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Deployment tiers | Local Docker + ECS only | Remove EC2 — 2 tiers sufficient |
| DynamoDB session key | `session_id` (PK) + `turn_timestamp` (SK) with hashed prefix | Avoid hot partitions under burst traffic |
| Embedding storage | Binary blob in DynamoDB metadata table | Future hybrid search, not used at query time (BM25 only in Phase 1-2.5) |
| Model deployment | Bake into Docker image (not downloaded at runtime) | Avoid cold start latency from model download |
| ECS task memory | 1024 MB (Phase 1 upgrade from 512 MB) | PyTorch + model = ~241 MB minimum; 512 MB causes OOM |
| Redis failure | Fallback to direct BM25 (never fail the turn) | Resilience requirement |
| Eval seed | Fixed (e.g., `random.seed(42)`) | Deterministic, reproducible gate results |

---

## New Requirements Added

| ID | Requirement |
|----|-------------|
| AGENT-01 | Orchestrator+Intent Agent: Claude routes each turn, logs intent + confidence |
| AGENT-02 | Retrieval Agent: Claude wraps BM25+DynamoDB RAG, returns top-3 chunks with source attribution |
| AGENT-03 | Response Agent: Claude synthesizes grounded answer with citations from retrieved context |
| AGENT-04 | Memory Store: DynamoDB session table with multi-turn history injected into context |
| AGENT-05 | Tool Agent: Mock in Phase 1.5, real municipal integrations in Phase 5 |
| AGENT-06 | Supervisor Agent: Claude vetoes unsafe plans, outputs signed audit trail with decision reason |
| OBS-04 | Agent trace events: per-turn JSON with intent, routing, retrieved docs, LLM tokens, latency |
| OBS-05 | Eval dashboard: CloudWatch with pass/fail filters (date, time range), sortable metric table |
| OBS-06 | Intent confusion matrix: per-intent precision/recall, logged per turn, aggregated weekly |
| OBS-07 | Cost breakdown per conversation: compute + LLM inference + storage, alert at 2x baseline |

---

## Open Questions (Resolved at Plan Time)

1. **Phase 1.5 Claude model:** Use `claude-haiku-4-5` for Orchestrator (fast, cheap) and `claude-sonnet-4-6` for Response Agent (quality)?
2. **Phase 5 tool data:** Where does the Jackson County property lookup API live? Need real endpoint before Phase 5 planning.
3. **Phase 2.5 memory window:** How many prior turns to inject into Orchestrator context? Start with 5, tune in Phase 3.
