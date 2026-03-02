# Phase 0 PRD (TPM View): Learning MVP Bootstrap

**Version:** 1.0  
**Date:** 2026-03-01  
**Phase:** `00-learning-mvp-bootstrap`  
**Primary audience:** Technical Product Manager, Engineering Manager, Data Scientist, Backend/Frontend Engineers

## 1) What This Document Is For

This document consolidates Phase 0 into one decision artifact:
- what was planned and completed
- what APIs exist and why
- how data is handled (and not handled)
- how to manually and automatically verify behavior
- what non-functional constraints apply
- how to reason about cost at MVP stage

It is written so non-technical stakeholders can follow intent and so engineers can execute and validate.

## 2) Phase 0 File Guide (What Each Document Is For)

| File | Purpose | When to read |
|---|---|---|
| `00-RESEARCH.md` | Why this architecture/approach was chosen | Before planning or when explaining tradeoffs |
| `00-CONTEXT.md` | Locked decisions and phase boundaries | Before replanning or when aligning stakeholders |
| `00-01-PLAN.md` | Backend gateway + auth/rate-limit plan | API surface review |
| `00-02-PLAN.md` | Adapter pipeline plan (ASR -> LLM -> TTS) | Voice orchestration review |
| `00-03-PLAN.md` | Frontend-to-backend integration plan | Web UX + integration review |
| `00-04-PLAN.md` | AWS bootstrap path plan | Deployment readiness review |
| `00-01..04-SUMMARY.md` | What was actually implemented | Completion audit |
| `00-VERIFICATION.md` | Must-have verification evidence | Sign-off checkpoint |
| `00-UAT.md` | Manual conversational UAT tracking | Human validation session |

## 3) Phase 0 Outcome Summary

### Goal
Deliver one complete, secure-enough MVP voice roundtrip and an initial AWS deployment path in `us-east-1`.

### What Was Completed
1. Backend API gateway with `/health`, `/chat`, `/ws`.
2. MVP auth + in-memory rate limiting.
3. Adapter-based orchestration with mock and AWS modes.
4. Frontend that only talks to backend APIs (no direct AWS calls).
5. Docker + Terraform + bootstrap script for AWS path.

### Requirement Coverage
- `API-00`: Complete
- `VOIC-01`: Complete
- `VOIC-02`: Complete (phase-0 interpretation: one-turn pipeline)
- `PLAT-00`: Complete

## 4) Scope and Boundaries

### In Scope (Phase 0)
- Browser voice/text to backend contract validation.
- One-turn orchestration path with mock/AWS adapters.
- MVP token validation and request throttling.
- Minimal repeatable AWS deployment bootstrap assets.

### Out of Scope (Deferred)
- Full IAM hardening and enterprise security controls.
- Persistent conversation storage and analytics warehousing.
- Formal latency SLO enforcement and deep observability dashboards.
- Advanced agentic/RAG capabilities.

## 5) Plan Breakdown as User Stories + Acceptance Criteria

| Plan | User story | Acceptance criteria |
|---|---|---|
| `00-01` | As a client app, I can call a stable backend API surface with protection controls. | `/health`, `/chat`, `/ws` exist; missing/invalid token rejected; rate limit returns `429`. |
| `00-02` | As a system, I can run ASR->LLM->TTS via swappable adapters so provider coupling stays low. | Pipeline order is enforced by tests; mock mode runs locally; AWS mode wiring exists. |
| `00-03` | As a user, I can send text/mic input from browser and receive backend-generated responses. | Frontend uses only `/chat` and `/ws`; no AWS SDK or credentials in frontend; e2e roundtrip passes. |
| `00-04` | As an operator, I can bootstrap a dev deployment path in AWS `us-east-1`. | Dockerfile + Terraform + bootstrap script + deploy smoke tests exist and execute in configured env. |

## 6) High-Level Architecture (Phase 0)

```text
Browser (frontend/index.html + app.js)
  |  REST /chat (text)
  |  WS   /ws   (audio/text events)
  v
FastAPI Backend (main.py + chat.py)
  |  auth.py (token validation)
  |  rate_limit.py (in-memory throttling)
  v
VoicePipeline (orchestrator/pipeline.py)
  |--> ASR Adapter (Mock or AWS Transcribe wrapper)
  |--> LLM Adapter (Mock or AWS Bedrock wrapper)
  |--> TTS Adapter (Mock or AWS Polly wrapper)
  v
Response events to client (partial_text, bot_text, bot_audio_chunk)

Deploy path:
Dockerfile -> ECR -> ECS Task/Service (Terraform) -> CloudWatch Logs
```

## 7) Data Handling and Storage: Where Data Lives Today

### Current State (Important)
- There is no persistent application database in Phase 0.
- Request/response payloads are processed in memory.
- Rate limiting state is in memory only (`InMemoryRateLimiter`), reset on process restart.
- `session_id` exists in `ChatRequest` schema but is not used for persisted session state yet.

### What You Can Inspect
- API responses directly from client calls.
- Frontend log panel output in `frontend/index.html`.
- Test outputs (`pytest`) for behavior validation.
- Cloud logs if deployed to ECS with CloudWatch.

### What You Cannot Inspect Yet
- Historical chat/session records (not implemented in this phase).
- Durable analytics for turns, intents, or latency distributions.

## 8) API Catalog (Business Purpose + Contract + Tests)

## API 1: `GET /health`

### Why this API exists
Provides a simple service liveliness check for local/dev automation and deployment smoke checks.

### User Story
As an operator, I can quickly verify backend availability before running functional tests.

### Contract
- Method: `GET`
- Auth: none
- Rate limit: none
- Response (200):

```json
{ "status": "ok" }
```

### Acceptance Criteria
1. Returns HTTP `200`.
2. Returns JSON with `status = "ok"`.

### Manual Test (PowerShell)
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## API 2: `POST /chat`

### Why this API exists
Provides a non-streaming text interface to the same LLM/TTS backend orchestration.

### User Story
As a client app, I can send text with auth and receive a backend-generated assistant reply.

### Contract
- Method: `POST`
- Auth: required `Authorization: Bearer <token>`
- Rate limit: required (path + token scoped)
- Request body:

```json
{
  "text": "hello",
  "session_id": "optional-string"
}
```

Notes:
- `text` is required, min length `1`, max `4000`.
- `session_id` is optional and currently not persisted.

- Success response (200):

```json
{
  "reply": "assistant:hello",
  "provider": "pipeline"
}
```

- Error response examples:
```json
{ "detail": "invalid or missing token" }   // 401
```
```json
{ "detail": "rate limit exceeded" }         // 429
```

### Acceptance Criteria
1. Missing token returns `401`.
2. Invalid token returns `401`.
3. Valid token returns `200` with `reply` string.
4. Requests above configured threshold return `429`.

### Manual Test (PowerShell)
```powershell
$token = "dev-token"

# Should fail (401)
Invoke-RestMethod -Method POST `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"text":"hello"}'

# Should pass (200)
Invoke-RestMethod -Method POST `
  -Uri http://127.0.0.1:8000/chat `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"text":"hello"}'
```

## API 3: `WS /ws`

### Why this API exists
Provides bidirectional low-latency channel for text and audio turn handling.

### User Story
As a browser voice client, I can open an authenticated WebSocket, stream audio chunks, and receive incremental response events.

### Contract
- Protocol: WebSocket
- Auth: token required via `?token=` query param or `Authorization: Bearer <token>`
- Rate limit: enforced at connection check

### Client -> Server message schema
```json
{
  "type": "start | audio_chunk | text | end",
  "text": "optional",
  "audio_base64": "optional"
}
```

### Server -> Client message schema
```json
{
  "type": "ack | partial_text | bot_text | bot_audio_chunk | error",
  "text": "optional",
  "audio_base64": "optional",
  "error": "optional"
}
```

### Typical event flow
1. Connect success -> `{"type":"ack","text":"connected"}`
2. Send `text` -> receive `bot_text`
3. Send `audio_chunk` -> receive `partial_text`, then `bot_text`, then `bot_audio_chunk`
4. Send `end` -> receive ack closed and socket closes

### Acceptance Criteria
1. Missing/invalid token cannot establish usable session.
2. Valid token receives `ack`.
3. Text messages produce `bot_text`.
4. Audio chunk messages produce `partial_text` + `bot_text` + `bot_audio_chunk` in order.

### Manual Test Options

Option A (recommended for TPM): UI-based
1. Start backend.
2. Open `frontend/index.html` through backend host.
3. Enter token, click `Connect WS`.
4. Use `Send Text` and `Start Mic`.
5. Confirm log panel shows expected WS event sequence.

Option B (engineer-level): Python websocket script
```python
import asyncio, json, websockets

async def main():
    uri = "ws://127.0.0.1:8000/ws?token=dev-token"
    async with websockets.connect(uri) as ws:
        print(await ws.recv())  # ack
        await ws.send(json.dumps({"type":"text","text":"ping"}))
        print(await ws.recv())  # bot_text
        await ws.send(json.dumps({"type":"end"}))
        print(await ws.recv())  # ack closed

asyncio.run(main())
```

## 9) WebSocket Event Matrix (Quick Reference)

| Direction | Type | Required fields | Meaning |
|---|---|---|---|
| client -> server | `start` | `type` | Reserved start event (phase-0 minimal handling) |
| client -> server | `text` | `type`, `text` | Send text turn |
| client -> server | `audio_chunk` | `type`, `audio_base64` | Send audio payload chunk |
| client -> server | `end` | `type` | End interaction |
| server -> client | `ack` | `type`, `text?` | Connection or close acknowledgment |
| server -> client | `partial_text` | `type`, `text` | Transcript fragment from ASR stage |
| server -> client | `bot_text` | `type`, `text` | Assistant text response |
| server -> client | `bot_audio_chunk` | `type`, `audio_base64` | Audio payload generated from TTS |
| server -> client | `error` | `type`, `error` | Error event (contracted but minimally used in phase 0) |

## 10) Non-Functional Requirements (Phase 0 Level)

### Security
- Token validation required on protected endpoints.
- Frontend must not hold AWS credentials.
- AWS calls stay server-side only.

### Reliability
- In-memory rate limit prevents basic abuse bursts.
- Local mocks allow deterministic behavior in dev/test.

### Performance
- Phase 0 validates flow correctness, not production latency SLO.
- Formal latency goals start in Phase 1 (`VOIC-03`).

### Operability
- Health endpoint and automated tests available.
- Container and Terraform bootstrap path available.

### Extensibility
- Adapter boundary allows future provider swap with minimal API surface changes.

## 11) Costing Model (Phase 0)

This phase should use a cost framework, not fixed pricing assumptions.

### Primary Cost Drivers
1. ECS/Fargate runtime (CPU/memory x runtime hours).
2. ECR storage and image transfer.
3. CloudWatch logs.
4. Optional AWS AI service usage (Transcribe, Bedrock, Polly) when mock mode is off.

### Suggested Estimation Formula
`Monthly Cost = Compute + Registry + Logs + AI Inference + Data Transfer`

Where:
- `Compute = task_hours * (cpu_rate + memory_rate)`
- `AI Inference = (audio_minutes * transcribe_rate) + (tokens * bedrock_rate) + (tts_chars * polly_rate)`
- `Logs = ingested_gb * log_rate`

### TPM Guidance
- Track baseline in three scenarios: low/demo, medium/internal testing, high/pre-prod rehearsal.
- Keep mock mode on by default for dev to avoid accidental inference spend.
- Add hard budget alerting in later phases (`REL-03`).

## 12) Success Criteria and Verification Evidence

### Business-Level Success
1. Team can demo one complete voice turn.
2. API boundary and auth/rate-limit controls are demonstrably working.
3. AWS deployment path is reproducible.

### Technical Evidence Already Present
- `tests/backend/test_backend_contracts.py`
- `tests/backend/test_orchestration_pipeline.py`
- `tests/e2e/test_phase0_roundtrip.py`
- `tests/e2e/test_aws_dev_deploy_smoke.py`
- `.planning/phases/00-learning-mvp-bootstrap/00-VERIFICATION.md`

### Recommended Validation Commands
```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -rs
scripts\run-backend.cmd
```

## 13) Glossary (Non-Technical Friendly)

| Term | Plain-language meaning |
|---|---|
| Adapter | A wrapper that lets us switch providers without rewriting app logic. |
| ASR | Speech-to-text conversion. |
| LLM | Language model that generates response text. |
| TTS | Text-to-speech conversion. |
| WebSocket | Two-way connection for real-time messages. |
| REST API | Standard request/response HTTP endpoint. |
| Orchestrator/Pipeline | The logic that runs ASR -> LLM -> TTS in order. |
| Rate limiting | A guard that blocks too many requests in a short time. |
| Fargate | AWS managed runtime to run containers without managing servers. |
| ECR | AWS container image registry. |
| Terraform | Infrastructure-as-code tool to define cloud resources. |

## 14) How TPMs Should Write This Type of PRD for EM + DS Audiences

Use this structure every time:
1. Problem + business objective (1 page max).
2. Scope boundaries (in-scope, out-of-scope).
3. User stories and acceptance criteria per capability/API.
4. Contracts (input/output examples, errors, auth).
5. Data handling (what is stored, where, retention, privacy).
6. NFRs (security, performance, reliability, cost).
7. Test plan (manual + automated).
8. Rollout and risks (dependencies, mitigations, open questions).

Authoring rules:
- Use tables for contracts and acceptance criteria.
- Keep each API section answerable by product + engineering + data teams.
- Distinguish current behavior from future-phase intent.
- Include exact commands for reproducible validation.

## 15) Appendix: Source of Truth Files

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-RESEARCH.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-CONTEXT.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-01-PLAN.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-02-PLAN.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-03-PLAN.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-04-PLAN.md`
- `.planning/phases/00-learning-mvp-bootstrap/00-VERIFICATION.md`
- `backend/app/main.py`
- `backend/app/api/chat.py`
- `backend/app/schemas/messages.py`
- `backend/app/security/auth.py`
- `backend/app/security/rate_limit.py`
