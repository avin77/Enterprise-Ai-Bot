Voice-Based Chatbot for PM (Gov-ready, Python, us-east-1)
================================================================

Objectives
----------
- Ship a secure, API-first web voice chatbot with low perceived latency, high reliability, and auditable controls.
- Align with NIST 800-53 Rev 5 and FedRAMP Moderate expectations (single-tenant now; `tenant_id` reserved for future).
- Keep costs low while enabling a streaming-first, pluggable ASR/TTS/LLM stack.

Definition of Done (Measurable)
--------------------------------
- Performance SLOs:
  - `time_to_first_partial_ms`: p50 <= 120 ms, p95 <= 250 ms.
  - `time_to_first_audio_ms`: p50 <= 300 ms, p95 <= 600 ms.
  - `turn_latency_ms`: p95 <= 2500 ms for standard FAQ turns.
- Reliability SLOs:
  - Monthly availability >= 99.0% for `/sessions` and `/ws/voice`.
  - WS connect success >= 99.5%; error budget tracked weekly.
- Quality and safety SLOs:
  - Golden dataset pass rate >= 95% on nightly run.
  - PII leakage rate = 0 in golden + jailbreak suites.
  - Hallucination score below agreed threshold for cited responses.
- Cost SLOs:
  - Cost per successful conversation within agreed budget cap.
  - Monthly cloud spend within configured service budgets.

Measurement Assumptions
-----------------------
- Baseline load: 100 concurrent sessions unless otherwise stated.
- Test client: modern desktop browser on broadband; mobile tracked separately.
- SLO evaluation window: rolling 30 days for availability, daily for latency/cost.

Scope and Defaults
------------------
- Region: `us-east-1` (cost and Bedrock/Transcribe/Polly availability).
- Runtime: Python FastAPI on ECS Fargate; Redis for session context.
- Data: Single tenant; schemas include optional `tenant_id` for later multi-tenant.
- LLMs: Bedrock Claude Sonnet (primary), Claude Haiku (supervisor).
- ASR/TTS: Amazon Transcribe and Polly default adapters; pluggable for provider swaps.
- RAG: OpenSearch Serverless (vector + keyword) with Titan embeddings; docs in S3 via ETL Lambda.
- Auth/Edge: API Gateway (REST + WebSocket), Cognito JWT, WAF, private VPC endpoints.

Architecture Highlights
-----------------------
- Orchestrator (Fargate): stateless tasks; Redis holds last 3 turns of transcript + tool outputs for fast recall.
- Pluggable services: `/services/asr.py`, `/services/tts.py`, `/services/llm.py`, `/services/rag.py`, `/services/guard.py`.
- Streaming-first loop: begin TTS as soon as first LLM tokens arrive; chunked WS back to client.
- Supervisor pattern: Haiku reviews tool plans/responses for policy and PII before execution/output.
- Observability: OpenTelemetry traces; structured JSON logs; CloudWatch + Grafana dashboards.

Security and Compliance Matrix (Initial)
----------------------------------------
| Domain | Control Objective | Implementation Artifact | Owner | Evidence/Gate |
|---|---|---|---|---|
| IAM | Least privilege | Terraform IAM modules + permission boundaries | Platform | Gate 0 review |
| Encryption | At-rest and in-transit encryption | KMS keys, TLS policies, service configs | Platform | Gate 0 review |
| Auditability | Immutable security-relevant logs | CloudWatch log groups, retention + export policy | Platform/Security | Gate 1 review |
| Data protection | PII detection and redaction | Guardrail service + supervisor checks | App | Gate 2 eval suite |
| Vulnerability management | Continuous scanning | CI SAST/dep scans + IaC scanning | Platform | Every PR |
| Change control | Traceable, approved changes | PR templates + commit history + release notes | TPM/Eng | Weekly rollup |

Threat Model and Guardrails
---------------------------
- Prompt injection: sanitize tool inputs, require allowlisted tool schemas, and enforce supervisor approval for risky actions.
- Tool abuse: per-tool auth scope checks, argument validation, rate limits, and policy-based deny rules.
- Data exfiltration: redact sensitive fields in logs, deny unapproved outbound calls, and restrict IAM/network egress.
- Authz boundaries: map JWT scopes to endpoint/tool permissions; reject missing/insufficient scopes.

Data and Storage Decisions
--------------------------
- Session state: choose one in Phase 0:
  - Option A: ElastiCache Redis OSS.
  - Option B: MemoryDB.
  Decision owner: Platform lead. Decision deadline: end of Phase 0, week 1.
- Vector/keyword search: OpenSearch Serverless (vector + BM25) using Titan embeddings.
  Index fields: `id`, `tenant_id?`, `source`, `doc_type`, `pii_flag`, `chunk_text`, `chunk_vector`, `created_at`, `emb_model`, `page_no`.
- Object storage: S3 buckets (KMS, versioned) for raw (`voice-raw`), processed/chunked (`voice-processed`), golden set (`voice-golden`), and logs/exports (`voice-logs`).
- Secrets/config: AWS Secrets Manager for secrets, SSM Parameter Store for non-secret config.
- No RDS/DynamoDB for MVP; revisit after Phase 2 based on tenancy and billing requirements.

Public Interfaces
-----------------
- REST: `/auth/token`, `/sessions`, `/knowledge` (upload/list/delete), `/metrics` (admin), `/callbacks`.
- WebSocket: `/ws/voice` messages `start`, `audio_chunk`, `client_event`, `partial_text`, `bot_text`, `bot_audio_chunk`, `end`, `error`.
- Internal tools (Phase 2): `/tools/property_lookup`, `/tools/ticket_recommendation`.
- Events: `conversation.completed`, `guardrail.blocked`, `handoff.requested`.

API and WS Contract Governance
------------------------------
- Versioning: semantic API version in path or header; WS message schema version in each envelope.
- Backward compatibility: no breaking field removals within minor versions; deprecations announced with sunset date.
- Error schema: normalized `code`, `message`, `trace_id`, `retryable`, `details`.
- Idempotency: required for mutating REST endpoints that may be retried.
- Auth scopes: explicit scope map per endpoint/message/tool; enforced server-side.

Metrics (CloudWatch/Grafana)
----------------------------
- Latency: `time_to_first_partial_ms`, `time_to_first_audio_ms`, `turn_latency_ms`, per-span (ASR/LLM/TTS).
- Reliability: `ws.connect_success`, `ws.disconnect_reason`, ASR/TTS error rates, 4xx/5xx, retry counts, circuit-breaker trips.
- Throughput: `concurrent_sessions`, `audio_chunks_per_sec`, `tokens_per_sec`.
- Quality/Speech: `asr.wer_est`, `asr.partial_latency_ms`, `asr.final_latency_ms`, `asr.vad_speech_ratio`, `asr.confidence_avg`, `tts.synth_latency_ms`, `tts.cache_hit`, `tts.audio_chunk_jitter_ms`.
- LLM/RAG: `llm.ttft_ms`, `llm.response_ms`, `llm.tokens_in/out`, `llm.cache_hit`, `llm.safety_blocks`, `llm.supervisor_veto`, `rag.citation_count`.
- Intent: `intent.detected`, `intent.confidence`, `intent.mismatch` (vs golden).
- Safety: guardrail blocks, PII detections, WAF blocks, auth failures.
- Cost: Bedrock tokens, Transcribe seconds, Polly chars, OpenSearch RU, data egress bytes, `cost_per_conversation_usd`.

Logs (structured JSON)
----------------------
- Request/trace: `trace_id`, `session_id`, `user_id`, `path`, `latency_ms`, `status`, `error_code`.
- ASR: `chunk_id`, partial/final text, confidence, `latency_ms`, `vad_speech_ratio`.
- LLM: model, tokens in/out, `ttft_ms`, cache hit, guardrail results, supervisor verdict.
- TTS: `voice_id`, chars, cache hit, `synth_latency_ms`.
- RAG/Tools: query, `top_k`, sources, citation count, `tool_name`, redacted `tool_args`, `tool_latency_ms`, status.
- Audit: user/session, action, hashed/redacted IO, policy decision (allow/deny), auth scope.
- Eval runs: `golden_id`, `wer`, `intent_match`, `citation_score`, `hallucination_score`, `latency_ms`, pass/fail.
- Sampling: verbose payload logs capped (for example 5%) in production; full detail in replay harness.

Golden Dataset and Reporting
----------------------------
- Storage: versioned S3 manifest + audio + references.
- Replay harness (CI/nightly): runs conversations through ASR/LLM/TTS; computes WER, intent match, citation/faithfulness, hallucination, latency; emits metrics (`golden.pass_rate`, `golden.wer_p50`, `golden.intent_match`, `golden.latency_p95`) and writes Parquet/CSV to S3.
- Dashboard: Golden Regression panel with last N runs and deltas.

Cost Guardrails
---------------
- Budget alerts:
  - 50% monthly budget: notify channel + review trend.
  - 80% monthly budget: enable conservative token/voice settings.
  - 95% monthly budget: auto-throttle non-critical workloads.
- Hard controls:
  - Per-session token caps and max turn duration.
  - Top-K limits for retrieval and bounded tool retries.
  - Sampling caps on high-volume logs.

Operations and DR
-----------------
- Incident response:
  - Sev 1 acknowledgement <= 15 minutes.
  - On-call rotation with runbooks for WS outage, ASR degradation, and Bedrock throttling.
- Backup/restore:
  - S3 versioning enabled; periodic restore tests from snapshot/export artifacts.
  - Redis persistence/backup approach documented after engine decision.
- DR posture (MVP): single-region with documented recovery runbook.
  - Target RTO <= 8 hours.
  - Target RPO <= 24 hours.

Phases
------
Phase 0 - Foundations and Golden Dataset (1-2 wks)
- Terraform baseline: VPC (private subnets), endpoints (Bedrock/S3/STS/OpenSearch), KMS keys, S3 buckets (audit, data), Redis, WAF skeleton, IAM least-privilege roles, Secrets Manager.
- CI: fmt/validate/tfsec/checkov + SAST/dep scan; pre-commit hooks.
- Contracts first: OpenAPI for REST; AsyncAPI/JSON schema for WS messages.
- Security baseline: threat model v1, scope-to-endpoint authz matrix, logging/retention policy.
- Golden dataset: 50 curated conversations (audio + expected transcript + intents + expected bot reply + citations) in S3 with manifest; fixtures in repo.
- Local dev: docker-compose with mocks for Transcribe/Polly/Bedrock, Redis, OpenSearch stub; sample `.env`.

Phase 1 - MVP Web Voice (4-6 wks)
- Frontend widget: WebRTC mic + VAD; OPUS/PCM streaming over WS; render partials and streamed audio; JWT auth.
- Edge/API: API Gateway REST + WS; Cognito; WAF basic rules; rate limits.
- Orchestrator: streaming ASR -> LLM -> TTS; prompt caching; PII scrub; safety guardrails; basic RAG over seeded FAQs.
- Observability: OTel traces; CloudWatch metrics/alarms; Grafana dashboards (latency, reliability, cost, safety).
- Tests: contract tests (REST/WS), adapter unit tests, golden-path latency script, golden dataset replay (non-stream) for regression.

Phase 2 - RAG-Driven Agentic Reliability (3-4 wks)
- Data ingest: S3 -> Lambda ETL -> OpenSearch; metadata (`doc_type`, PII flags, optional `tenant_id`).
- Agentic tools: `property_lookup`, `ticket_recommendation`; orchestrator plans + executes; fuse replies with citations.
- Supervisor: Haiku vetoes policy-violating tool calls/responses.
- Evaluations: WER, intent match, citation/faithfulness, hallucination, PII leakage, jailbreak suites, tool success, latency/load/chaos tests.
- Performance: OpenSearch tuning, Redis sizing, keep-alive WS, cache frequent prompts/voices.
- Reliability: circuit breakers, retries/backoff, fallback to text-only mode.

Stage Gates (TPM tracking)
--------------------------
- Gate 0: Terraform baseline + contracts + golden dataset + threat model v1 approved.
- Gate 1: MVP streaming loop demo (partial -> TTS) with latency dashboard and SLO measurement report.
- Gate 2: RAG + supervisor passing eval suite; safety/quality dashboards populated; API/WS contract conformance report complete.
- Weekly rollup: latency, cost, safety blocks, WER, hallucination percentage, tool success rate, error-budget burn.

Decision Log (Open)
-------------------
- Locale support in Phase 1: non-`en-US` needed? Owner: Product. Due: before Phase 1 build lock.
- Telephony/IVR scope: keep out of scope for MVP unless explicitly added. Owner: Product.
- Backend confirmation: Python FastAPI remains default unless changed by architecture review. Owner: Engineering.
- Redis engine choice: ElastiCache vs MemoryDB. Owner: Platform. Due: Phase 0 week 1.
