# Feature Research

**Domain:** Gov-ready web voice AI assistant
**Researched:** 2026-02-28
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Authenticated web voice session | Required for enterprise/government use | MEDIUM | JWT auth and scope checks are baseline |
| Streaming partial transcript and audio response | Core voice UX expectation | HIGH | Must optimize TTFT and first-audio latency |
| Contracted REST and WS interfaces | Needed for integration governance | MEDIUM | OpenAPI and WS schema versioning required |
| Security guardrails and PII handling | Mandatory for gov contexts | HIGH | Must include supervisor and redaction controls |
| Observable SLO metrics and alarms | Required for operations and audits | MEDIUM | Dashboards and alerts are non-optional |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Citation-backed RAG responses | Increases trust and factual grounding | HIGH | Requires retrieval quality and source tracking |
| Supervisor-vetoed tool calls | Reduces policy and exfiltration risk | HIGH | Requires deterministic policies and review hooks |
| Golden dataset replay with quality scoring | Improves release confidence | MEDIUM | Enables continuous quality/safety regression checks |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Telephony/IVR in MVP | Broader channel coverage | Splits focus and adds integration complexity early | Defer to later milestone after web MVP stabilizes |
| Broad multi-language launch | More reach | Increases ASR/TTS tuning and quality burden before baseline | Start with en-US and evaluate expansion post-MVP |
| Full multi-tenant isolation in MVP | Enterprise roadmap pressure | Significant data/auth complexity too early | Keep single-tenant with tenant_id reserved |

## MVP Definition

### Launch With (v1)

- [ ] Secure infrastructure baseline and contract-first APIs
- [ ] Web voice streaming loop (ASR -> LLM -> TTS)
- [ ] Basic FAQ RAG with citations
- [ ] Core observability, golden dataset, and baseline evaluations

### Add After Validation (v1.x)

- [ ] Additional tool integrations beyond initial two tools
- [ ] Advanced retrieval tuning and response caching expansion

### Future Consideration (v2+)

- [ ] Telephony/IVR channel support
- [ ] Multi-language support
- [ ] Full multi-tenant isolation model

## Sources

- PLAN.md in repository - objectives, constraints, and phase proposals

---
*Feature research for: Gov-ready web voice AI assistant*
*Researched: 2026-02-28*
