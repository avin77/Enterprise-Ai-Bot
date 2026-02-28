# Architecture Research

**Domain:** Gov-ready web voice AI assistant
**Researched:** 2026-02-28
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
+------------------------------ Client Layer ------------------------------+
| Web widget (mic/VAD), auth token handling, partial text/audio rendering |
+----------------------------------+--------------------------------------+
                                   |
+------------------------------ Edge Layer --------------------------------+
| API Gateway REST + WebSocket, Cognito JWT auth, WAF/rate limits         |
+----------------------------------+--------------------------------------+
                                   |
+-------------------------- Orchestrator Layer ----------------------------+
| FastAPI service adapters: ASR, LLM, TTS, RAG, guard, supervisor         |
| Streaming pipeline with tool planning/validation and response fusion     |
+----------------------------------+--------------------------------------+
                                   |
+------------------------------ Data Layer --------------------------------+
| Redis session context | OpenSearch vector+keyword | S3 datasets/docs     |
| CloudWatch/Grafana/OTel telemetry and audit logs                         |
+-------------------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Web widget | Capture audio, send chunks, render partial/final outputs | Browser app with WS transport and VAD |
| API edge | Authenticate requests and enforce perimeter policy | API Gateway + Cognito + WAF |
| Orchestrator | Manage ASR->LLM->TTS flow and tool decisions | FastAPI async service on ECS Fargate |
| Guard/supervisor | Block unsafe prompts/tools/outputs | Policy layer + secondary model review |
| Retrieval | Fetch grounded context with citations | OpenSearch Serverless + embeddings |
| Session memory | Retain short-turn context | Redis with bounded history |

## Recommended Project Structure

```
app/
|-- api/
|-- orchestrator/
|-- services/
|   |-- asr.py
|   |-- tts.py
|   |-- llm.py
|   |-- rag.py
|   `-- guard.py
|-- schemas/
|-- tools/
|-- observability/
`-- tests/
infra/
|-- terraform/
`-- policies/
```

## Data Flow

1. Client opens authenticated WS session and streams audio chunks.
2. ASR returns partial/final transcript events.
3. LLM generates response; orchestrator starts TTS as soon as first safe tokens are available.
4. If retrieval/tooling is required, supervisor reviews plan and output before release.
5. Bot text and audio chunks stream back to client; traces/metrics/logs are emitted.

## Anti-Patterns

- Building tool execution without strict schemas and authz checks.
- Logging raw sensitive payloads without redaction policy.
- Treating retrieval and citation as optional for high-trust government answers.

## Sources

- PLAN.md in repository - architecture highlights and interface contracts

---
*Architecture research for: Gov-ready web voice AI assistant*
*Researched: 2026-02-28*
