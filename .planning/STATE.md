# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Deliver fast, secure, and auditable voice conversations that agencies can trust in production.
**Current focus:** Runnable MVP Web Voice

## Current Position

Phase: 1 of 10 (Runnable MVP Web Voice)
Plan: 3 of 4 in current phase
Status: In progress
Last activity: 2026-03-10 - Executed Plan 01-03 (ECS task definition, IAM policy, FAQ loader, ConversationSession)

Progress: [###-------] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 34 min
- Total execution time: 2.8 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 (Learning MVP Bootstrap) | 5 | 170 min | 34 min |
| 1 (Runnable MVP Web Voice) | 3 | 12 min | 4 min |

**Recent Trend:**
- Last 5 plans: 00-05 (local execution), 01-01 (`cf2bf0a`), 01-02 (plan), 01-03 (`609f56a`)
- Trend: Strong throughput with Phase 1 in progress

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 0]: Prioritize runnable MVP learning flow before full security hardening
- [Phase 0]: Keep frontend backend-only and block direct cloud SDK/credential usage in client code
- [Phase 0]: Use adapter boundaries (ASR/LLM/TTS) with default mock mode and AWS switch via environment
- [Phase 0]: Ship AWS bootstrap with Docker + Terraform + scriptable bring-up while deferring hardening scope
- [Phase 3]: Add formal evaluation gate before starting RAG implementation
- [Phase 6]: Add second evaluation gate before enabling agentic tooling
- [Phase 7-8]: Split tool functionality from agentic safety governance
- [Phase 1, Plan 01-01]: Docker build context must be repo root (not ./backend) because existing Dockerfile uses COPY backend/ paths
- [Phase 1, Plan 01-01]: USE_AWS_MOCKS=true as default for safe local dev; AWS_REGION defaults to ap-south-1
- [Phase 1, Plan 01-03]: ECS memory locked at 1024MB — sentence-transformers OOM-kills at 512MB with PyTorch
- [Phase 1, Plan 01-03]: Redis sidecar essential=false — orchestrator must not fail when Redis is unavailable
- [Phase 1, Plan 01-03]: Conversation DynamoDB write is fire-and-forget — voice latency must not depend on DynamoDB
- [Phase 1, Plan 01-03]: /metrics endpoint shape locked (p50/p95/p99 per stage) as stub for Plan 01-04

### Pending Todos

None yet.

### Blockers/Concerns

- Local sandbox blocks atomic file replace operations used by `py_compile`; syntax verification was performed via in-memory compile checks.
- Local sandbox/tooling lacks AWS CLI credentials for live deploy checks; infrastructure smoke tests run in local-asset mode with optional live URL checks.

## Session Continuity

Last session: 2026-03-10 16:30
Stopped at: Completed 01-03-PLAN.md (ECS task definition, IAM policy, FAQ loader, ConversationSession DynamoDB tracking)
Resume file: .planning/phases/01-runnable-mvp-web-voice/01-03-SUMMARY.md
