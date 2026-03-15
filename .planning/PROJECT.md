# Enterprise AI Voice Bot

## What This Is

This project delivers a government-ready, API-first voice chatbot for web channels with streaming speech interactions and auditable controls. The system is designed for secure operation in AWS us-east-1 and aligns implementation choices with NIST 800-53 Rev 5 and FedRAMP Moderate expectations. It prioritizes low perceived latency, reliability, and cost controls while keeping the architecture modular.

## Core Value

Deliver fast, secure, and auditable voice conversations that agencies can trust in production.

## Requirements

### Validated

(None yet - ship to validate)

### Active

- [ ] Secure cloud baseline with least-privilege IAM, encryption, and auditability
- [ ] Streaming ASR -> LLM -> TTS voice loop over authenticated WebSocket sessions
- [ ] Contract-first REST and WS interfaces with versioning and error standards
- [ ] RAG with citations and supervised tool-calling safety checks
- [ ] Golden dataset replay and quality/safety evaluation reporting
- [ ] Reliability and cost guardrails with measurable SLO tracking

### Out of Scope

- Telephony/IVR channels in MVP - explicitly deferred unless added as a future phase
- Full multi-tenant isolation in MVP - `tenant_id` is reserved but not activated
- RDS/DynamoDB for MVP runtime state - deferred pending post-Phase-2 evidence

## Context

- Target environment is AWS us-east-1 with FastAPI on ECS Fargate, Redis session context, OpenSearch Serverless, Bedrock Claude models, Amazon Transcribe, and Polly.
- Public interfaces include REST endpoints for auth/session/knowledge/metrics and a WebSocket endpoint for bidirectional voice events.
- Security posture emphasizes prompt-injection defense, tool allowlisting, authz scope enforcement, PII redaction, and immutable security-relevant logs.
- Success is measured by latency, reliability, quality/safety, and cost SLOs defined in PLAN.md.

## Constraints

- **Compliance**: NIST 800-53 Rev 5 and FedRAMP Moderate alignment - required for gov readiness.
- **Region**: AWS us-east-1 only - service availability and cost assumptions are tied to this region.
- **Runtime**: Python FastAPI on ECS Fargate - architecture and deployment choices must stay compatible.
- **Interfaces**: Contract-first OpenAPI/AsyncAPI governance - integration stability depends on schema discipline.
- **Operational**: Monthly availability >= 99.0 percent and strict latency SLOs - implementation must preserve these targets.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use AWS us-east-1 for MVP | Matches service availability, cost profile, and compliance planning | - Pending |
| Keep single-tenant design with reserved tenant_id | Reduces MVP complexity while preserving expansion path | - Pending |
| Use Bedrock Sonnet primary + Haiku supervisor | Balances quality and policy supervision needs | - Pending |
| Use OpenSearch Serverless for vector + keyword retrieval | Supports citation-ready hybrid retrieval without extra datastore sprawl | - Pending |
| Treat telephony/IVR as out of MVP scope | Focuses effort on web voice quality and reliability first | - Pending |

---
*Last updated: 2026-02-28 after initialization*
