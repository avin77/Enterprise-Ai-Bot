---
phase: 01-runnable-mvp-web-voice
plan: 03
subsystem: infra
tags: [ecs, fargate, dynamodb, iam, bm25, conversation-tracking, slo, ttl]

# Dependency graph
requires:
  - phase: 01-02
    provides: PipelineResult dataclass with asr_ms/rag_ms/llm_ms/tts_ms timing fields

provides:
  - ECS task definition with 1024MB/512CPU and Redis sidecar for ap-south-1 Fargate deployment
  - IAM task role policy with all 9 ROADMAP.md permissions plus Bedrock/Transcribe/Polly
  - FAQ loader CLI (BatchWriteItem) for DynamoDB voicebot-faq-knowledge table
  - ConversationSession class + write_conversation_turn() for DynamoDB voicebot-conversations
  - /metrics endpoint stub (asr/rag/llm/tts with p50/p95/p99 shape)
  - Conversation tracking wired into WebSocket handler (only when USE_AWS_MOCKS=false)

affects: [01-04, 01.5-agentic-voice-core, 02-public-sector-safety]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conversation tracking lives in WebSocket handler (main.py), not VoicePipeline — keeps pipeline.py pure and testable without DynamoDB"
    - "slo_met flag set at write time (total_ms < 1500) — single source of truth for SLO compliance"
    - "DynamoDB TTL = epoch + 90*86400 — enforced by DynamoDB attribute-level expiry"
    - "rag_chunks_used stored as DynamoDB SS (non-empty) or NULL — avoids empty StringSet error"
    - "ECS sidecar pattern: Redis essential=false so orchestrator continues if Redis fails"

key-files:
  created:
    - infra/ecs_task_definition.json
    - infra/iam_task_role_policy.json
    - knowledge/scripts/load_faqs.py
    - knowledge/data/local/sample_faqs.json
    - backend/app/services/conversation.py
    - tests/backend/test_infra_config.py
    - tests/backend/test_conversation.py
  modified:
    - backend/app/orchestrator/pipeline.py
    - backend/app/main.py
    - tests/e2e/test_aws_dev_deploy_smoke.py

key-decisions:
  - "ECS memory locked at 1024MB (512MB causes OOM with PyTorch/sentence-transformers all-MiniLM-L6-v2)"
  - "Redis sidecar essential=false — orchestrator must not fail if Redis is unavailable (BM25 fallback)"
  - "DynamoDB conversation write is fire-and-forget with try/except — voice latency must not be impacted by DynamoDB failures"
  - "/metrics returns stable shape (p50/p95/p99 per stage) as stub — Plan 01-04 fills in real values"

patterns-established:
  - "Pipeline purity pattern: VoicePipeline has no DynamoDB side effects; conversation tracking is the handler's responsibility"

requirements-completed: [VOIC-03, RAG-01, RAG-02]

# Metrics
duration: 7min
completed: 2026-03-10
---

# Phase 1 Plan 03: ECS Deploy + IAM + FAQ Loader + Conversation Tracking Summary

**ECS Fargate task definition (1024MB/512CPU + Redis sidecar), IAM policy with 9+6 permissions, DynamoDB FAQ loader, and ConversationSession tracking with TTL and slo_met flag**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-10T16:23:26Z
- **Completed:** 2026-03-10T16:30:20Z
- **Tasks:** 2
- **Files modified:** 10 (7 created, 3 modified)

## Accomplishments

- ECS task definition specifies 1024MB memory (LOCKED — prevents OOM with PyTorch) and 512 CPU units, with orchestrator + Redis sidecar in same Fargate task
- IAM task role policy grants all 9 ROADMAP.md required permissions plus Bedrock inference, Transcribe streaming, and Polly TTS (16 total actions)
- ConversationSession class generates `sess_{8-hex}` IDs and tracks incremental turn_number; write_conversation_turn() stores per-stage timing, slo_met flag (threshold 1500ms), and TTL 90 days
- /metrics endpoint added with stable asr/rag/llm/tts shape (p50/p95/p99) — stub returns zeros, Plan 01-04 fills real values
- Conversation tracking wired into WebSocket handler (fire-and-forget, skipped when USE_AWS_MOCKS=true)

## Task Commits

Each task was committed atomically:

1. **Task 1: ECS task definition + IAM policy + FAQ loader** - `a1c49cb` (feat)
2. **Task 2: ConversationSession DynamoDB tracking** - `609f56a` (feat)

_Both tasks used TDD approach: test files written first (RED), then implementation (GREEN)._

## Files Created/Modified

- `infra/ecs_task_definition.json` - FARGATE task definition: memory=1024, cpu=512, orchestrator + Redis sidecar
- `infra/iam_task_role_policy.json` - IAM policy: 9 ROADMAP permissions + Bedrock/Transcribe/Polly (16 actions total)
- `knowledge/scripts/load_faqs.py` - CLI loader: reads sample_faqs.json, uses BatchWriteItem (25-item batches), supports --dry-run
- `knowledge/data/local/sample_faqs.json` - 8 sample FAQs: tax (2), voter (2), permit (2), utility (1), general (1)
- `knowledge/__init__.py` - Package init for knowledge module
- `knowledge/scripts/__init__.py` - Package init for scripts module
- `backend/app/services/conversation.py` - ConversationSession + write_conversation_turn() with TTL, slo_met, truncation
- `backend/app/orchestrator/pipeline.py` - Added design comment: conversation tracking belongs in handler, not pipeline
- `backend/app/main.py` - ConversationSession per WS connection, /metrics stub endpoint, DynamoDB fire-and-forget writes
- `tests/backend/test_infra_config.py` - 7 tests verifying ECS/IAM/loader config
- `tests/backend/test_conversation.py` - 7 tests replacing Wave 0 skip stub (slo_met, TTL, truncation, chunk formats)
- `tests/e2e/test_aws_dev_deploy_smoke.py` - Added test_metrics_endpoint_structure (GET /metrics shape check)

## Decisions Made

- **1024MB memory locked** — sentence-transformers all-MiniLM-L6-v2 PyTorch model OOM-kills at 512MB; 1024MB confirmed safe
- **Redis essential=false** — orchestrator must survive Redis failure (BM25 direct query is the fallback path in Plan 01-02)
- **Conversation write is fire-and-forget** — `try/except` around DynamoDB write in WebSocket handler; DynamoDB latency must never add to voice turn latency
- **/metrics stub with stable contract** — returns zeros now, but the shape (asr/rag/llm/tts with p50/p95/p99) is locked so Plan 01-04 can populate without downstream breakage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added /metrics endpoint to main.py**
- **Found during:** Task 2 (smoke test addition)
- **Issue:** Plan specified `test_metrics_endpoint_structure` smoke test requiring GET /metrics with asr/rag/llm/tts + p50/p95/p99 shape, but no /metrics endpoint existed in main.py
- **Fix:** Added /metrics stub endpoint returning zeros with the required shape; annotated as Phase 1 stub
- **Files modified:** backend/app/main.py
- **Verification:** test_metrics_endpoint_structure PASSES
- **Committed in:** 609f56a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical endpoint required by own test)
**Impact on plan:** Necessary for correctness — the plan's own smoke test required the endpoint. No scope creep.

## ECS task definition key values

| Field | Value |
|-------|-------|
| memory | 1024 MB |
| cpu | 512 units |
| executionRoleArn | arn:aws:iam::148952810686:role/ecsTaskExecutionRole |
| taskRoleArn | arn:aws:iam::148952810686:role/voicebot-task-role |
| orchestrator container | 900MB / 460 CPU |
| Redis sidecar | 60MB / 50 CPU, essential=false |

## IAM permissions summary

9 ROADMAP.md required: dynamodb:Scan, GetItem, Query, PutItem, BatchWriteItem, UpdateItem, s3:GetObject, s3:ListBucket, cloudwatch:PutMetricData

6 RESEARCH.md additions: bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream, transcribe:StartStreamTranscription, transcribe:StartStreamTranscriptionWebSocket, polly:SynthesizeSpeech, polly:DescribeVoices

## Conversation tracking schema

| DynamoDB attribute | Type | Notes |
|--------------------|------|-------|
| session_id | S (PK) | sess_{8-hex-uuid} |
| turn_number | N (SK) | 1, 2, 3... |
| user_input | S | truncated to 2000 chars |
| assistant_response | S | truncated to 4000 chars |
| asr_ms / rag_ms / llm_ms / tts_ms | N | rounded to 2 decimal places |
| total_ms | N | sum of 4 stage timings |
| slo_met | BOOL | True when total_ms < 1500 |
| ttl | N | epoch + 90*86400 (DynamoDB auto-expires) |
| rag_chunks_used | SS or NULL | SS when non-empty, NULL otherwise |
| timestamp | S | ISO 8601 UTC |

## load_faqs.py usage

```bash
# Dry run (no AWS calls needed)
python knowledge/scripts/load_faqs.py --dry-run

# Load to AWS (requires IAM credentials)
python knowledge/scripts/load_faqs.py --table voicebot-faq-knowledge --region ap-south-1

# Custom path
python knowledge/scripts/load_faqs.py --faq-path knowledge/data/local/sample_faqs.json
```

## Issues Encountered

None — both tasks executed cleanly. Pre-existing test failures in test_bm25_redis.py, test_knowledge_adapter.py (Wave 0 stubs), and test_bootstrap_script tests are out of scope for Plan 01-03.

## Next Phase Readiness

- Plan 01-04 (metrics + monitoring) can now read the /metrics endpoint contract and populate real latency percentiles
- ECS task definition ready to register: `aws ecs register-task-definition --cli-input-json file://infra/ecs_task_definition.json`
- IAM policy ready to attach: `aws iam put-role-policy --role-name voicebot-task-role --policy-name voicebot-task-policy --policy-document file://infra/iam_task_role_policy.json`
- FAQ knowledge base ready to load: `python knowledge/scripts/load_faqs.py`

---
*Phase: 01-runnable-mvp-web-voice*
*Completed: 2026-03-10*
