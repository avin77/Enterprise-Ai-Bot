---
phase: 1
slug: runnable-mvp-web-voice
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` — Wave 0 creates it |
| **Quick run command** | `python -m pytest tests/backend/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15s quick / ~60s full |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/backend/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + manual ECS smoke test
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | RAG-01 | unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_bm25_index_builds -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | RAG-02 | unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_rag_llm_adapter_injects_context -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | VOIC-03 | unit | `python -m pytest tests/backend/test_latency_probes.py::test_pipeline_result_has_timing_fields -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | RAG-01 | unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_dynamo_uses_paginator -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | RAG-01 | unit | `python -m pytest tests/backend/test_knowledge_adapter.py::test_faq_item_has_required_fields -x -q` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | RAG-02 | unit | `python -m pytest tests/backend/test_bm25_redis.py::test_redis_fallback_on_failure -x -q` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | RAG-02 | unit | `python -m pytest tests/backend/test_bm25_redis.py::test_expand_government_query_adds_synonyms -x -q` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | RAG-02 | unit | `python -m pytest tests/backend/test_bm25_redis.py::test_retrieve_returns_source_attribution -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | VOIC-03 | unit | `python -m pytest tests/backend/test_conversation.py::test_slo_flag_set_on_turn_write -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 3 | VOIC-03 | unit | `python -m pytest tests/backend/test_latency_probes.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 3 | RAG-01+RAG-02 | e2e | `python -m pytest tests/e2e/test_phase1_roundtrip.py -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 4 | VOIC-03 | manual | `aws ecs describe-task-definition --task-definition voice-bot-mvp --region ap-south-1` | N/A | ⬜ pending |
| 1-04-02 | 04 | 4 | VOIC-03 | smoke | `python -m pytest tests/e2e/test_aws_dev_deploy_smoke.py -x -q -k "latency"` | Extend existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/backend/test_knowledge_adapter.py` — stubs for RAG-01, RAG-02 (BM25 index build, DynamoDB paginator, RAGLLMAdapter injection)
- [ ] `tests/backend/test_bm25_redis.py` — stubs for RAG-02 (Redis fallback, query expansion, source attribution)
- [ ] `tests/backend/test_conversation.py` — stubs for VOIC-03 (ConversationSession, turn write, slo_met flag)
- [ ] `tests/backend/test_latency_probes.py` — stubs for VOIC-03 (PipelineResult timing fields, SLO calculation with mock adapters)
- [ ] `tests/e2e/test_phase1_roundtrip.py` — stubs for RAG-01+RAG-02+VOIC-03 (full voice turn with mock adapters, asserts sources present)
- [ ] `pytest.ini` — root-level pytest configuration (`testpaths`, `asyncio_mode=auto` for pytest-asyncio)
- [ ] `backend/requirements.txt` — add `pytest-asyncio>=0.23`

*Existing infrastructure from Phase 0 (no changes required):*
- `tests/backend/test_backend_contracts.py` — Phase 0 contracts, unaffected
- `tests/backend/test_orchestration_pipeline.py` — VoicePipeline unit tests, unaffected if RAG stage is additive

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ECS task memory set to 1024 MB | VOIC-03 (SC-5) | Infrastructure state not testable with pytest | `aws ecs describe-task-definition --task-definition voice-bot-mvp --region ap-south-1 \| grep memory` |
| IAM role includes all required permissions | VOIC-03 (SC-6) | IAM policy simulation requires live AWS | `aws iam simulate-principal-policy` for each of: dynamodb:Scan, GetItem, Query, PutItem, BatchWriteItem, UpdateItem, s3:GetObject, s3:ListBucket, cloudwatch:PutMetricData |
| Bot answers Jackson County FAQs correctly | RAG-01 (SC-1) | Semantic correctness requires human review | Ask 5 real Jackson County FAQ questions via voice interface; verify answers cite source documents |

---

## Success Criterion → Test Coverage

| Success Criterion | Automated Test | Manual Check |
|-------------------|---------------|--------------|
| 1. FAQs answered correctly via RAG | `test_phase1_roundtrip.py` (mock) | Human FAQ validation session |
| 2. RAGLLMAdapter injects top-3 chunks | `test_knowledge_adapter.py::test_rag_llm_adapter_injects_context` | — |
| 3. Turn latency <1.5s p95 measured per-stage | `test_latency_probes.py` (mock, <100ms) | ECS smoke: `test_aws_dev_deploy_smoke.py -k latency` |
| 4. Same codebase local + ECS (config only) | `test_phase1_roundtrip.py` local run | ECS smoke test green |
| 5. ECS task 1024 MB memory | — | `aws ecs describe-task-definition` |
| 6. IAM role has all permissions | — | `aws iam simulate-principal-policy` |
| 7. Redis failure → BM25 fallback (no exception) | `test_bm25_redis.py::test_redis_fallback_on_failure` | — |
| 8. Government synonyms ≥30 pairs | `test_bm25_redis.py::test_expand_government_query_adds_synonyms` + count assertion | — |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
