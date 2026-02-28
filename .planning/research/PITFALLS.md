# Pitfalls Research

**Domain:** Gov-ready web voice AI assistant
**Researched:** 2026-02-28
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Latency regression from non-streaming orchestration

**What goes wrong:**
Users experience long pauses before first transcript/audio output.

**Why it happens:**
Teams wait for full model completion before TTS and response emission.

**How to avoid:**
Implement token-streaming LLM integration and begin TTS at first safe token window.

**Warning signs:**
p95 `time_to_first_audio_ms` trends above SLO threshold.

**Phase to address:**
Phase 1

---

### Pitfall 2: Unsafe tool calls and data exfiltration paths

**What goes wrong:**
Prompt injection drives unauthorized tool usage or sensitive output leakage.

**Why it happens:**
Tool schemas and policy checks are incomplete or bypassed.

**How to avoid:**
Use strict allowlisted tool schemas, auth scope checks, and supervisor veto gates.

**Warning signs:**
Unexpected tool argument patterns or policy denies rising in logs.

**Phase to address:**
Phase 2

---

### Pitfall 3: Compliance drift from weak audit and retention controls

**What goes wrong:**
Security events cannot be reconstructed for reviews or incidents.

**Why it happens:**
Logging lacks consistent structure, retention policy, and redaction discipline.

**How to avoid:**
Define structured JSON logging schema, retention policy, export path, and redaction defaults early.

**Warning signs:**
Missing trace IDs across requests or inconsistent event fields.

**Phase to address:**
Phase 0

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded retries | Cascading latency and cost spikes | Circuit breakers + bounded backoff | During upstream service degradation |
| Oversized retrieval context | Slow response generation, token overuse | Tune top-k and chunk size, cache hot paths | As traffic and corpus size grow |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging raw tool args with sensitive fields | PII and policy exposure | Redact/hash sensitive fields before log emit |
| Missing per-tool auth scope mapping | Privilege escalation | Enforce explicit scope matrix in orchestrator |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Latency regression from non-streaming orchestration | Phase 1 | SLO dashboards and golden latency replay |
| Unsafe tool calls and data exfiltration paths | Phase 2 | Supervisor veto metrics and jailbreak suite results |
| Compliance drift from weak audit controls | Phase 0 | Gate review and audit log checks |

## Sources

- PLAN.md in repository - threat model, SLOs, and operational controls

---
*Pitfalls research for: Gov-ready web voice AI assistant*
*Researched: 2026-02-28*
