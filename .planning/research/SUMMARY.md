# Project Research Summary

**Project:** Voice-Based Chatbot for Granicus PM
**Domain:** Gov-ready web voice AI assistant
**Researched:** 2026-02-28
**Confidence:** HIGH

## Executive Summary

The project should be built as a streaming-first web voice assistant with strict security and observability controls from day one. The recommended architecture is AWS-native: API Gateway + Cognito + WAF at the edge, FastAPI orchestrator on ECS Fargate, Redis session context, and OpenSearch Serverless for citation-backed retrieval.

The roadmap should prioritize foundations and contract governance first, then ship end-to-end streaming voice functionality, then add higher-risk agentic/RAG reliability features with supervisor enforcement and evaluation depth. This order reduces compliance and reliability risk while preserving delivery speed.

## Key Findings

### Recommended Stack

- FastAPI on ECS Fargate for orchestrator logic
- API Gateway REST/WS with Cognito JWT and WAF for secure ingress
- Bedrock Sonnet for primary generation and Haiku supervisor for safety review
- OpenSearch Serverless and Titan embeddings for hybrid retrieval and citations
- OpenTelemetry + CloudWatch/Grafana for SLO measurement and operations

### Expected Features

**Must have (table stakes):**
- Authenticated streaming voice session with partial text and audio output
- Contract-first API and WS schema governance
- Security guardrails, redaction, and auditability

**Should have (competitive):**
- Citation-backed RAG responses
- Supervisor-vetoed tool execution
- Golden dataset replay with quality/safety metrics

**Defer (v2+):**
- Telephony/IVR channel support
- Multi-language support
- Full multi-tenant isolation model

### Architecture Approach

Use a layered architecture with clear boundaries between client, edge, orchestrator, and data services. Keep orchestrator stateless, push short-term conversational context to Redis, and enforce policy checks before tool execution and final response release.

### Critical Pitfalls

1. Latency regressions when streaming is not implemented end-to-end
2. Unsafe tool execution without strict schema + authz + supervisor checks
3. Compliance drift from weak logging/redaction/retention controls

## Implications for Roadmap

### Phase 0: Foundations and Golden Dataset
**Rationale:** Establishes secure baseline and contracts needed for all later work.

### Phase 1: MVP Web Voice
**Rationale:** Delivers core product value with streaming voice interactions and observability.

### Phase 2: RAG-Driven Agentic Reliability
**Rationale:** Adds high-complexity retrieval/tools/supervisor features after stable MVP loop exists.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Browser audio transport and streaming UX tuning details
- **Phase 2:** Tool safety policy design and retrieval quality optimization

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Matches explicit constraints in PLAN.md |
| Features | HIGH | Directly grounded in objectives and phases |
| Architecture | HIGH | Detailed architecture already captured in PLAN.md |
| Pitfalls | HIGH | Risks and controls are explicitly documented |

**Overall confidence:** HIGH

---
*Research completed: 2026-02-28*
*Ready for roadmap: yes*
