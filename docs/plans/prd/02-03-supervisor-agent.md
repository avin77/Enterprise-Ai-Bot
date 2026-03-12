# PRD: Supervisor Agent + Signed Audit Trail + API Hardening — Plan 02-03

**Phase:** 02 — Public Sector Safety
**Status:** Planned
**Owner:** Engineering
**Date:** 2026-03-12

---

## Problem Statement

Guardrails in the system prompt are a soft defence — the Response Agent can still produce unsafe content if the prompt is adversarially crafted. There is also no audit record of safety incidents, which is required for government accountability. Finally, the API has no rate limiting, meaning a single bad actor could flood the service or enumerate the knowledge base.

---

## Goals

- Add an independent AI reviewer (Supervisor Agent) that vetoes unsafe responses before they reach the user
- Write a tamper-evident audit record to DynamoDB for every vetoed response
- Add rate limiting to HTTP and WebSocket endpoints
- Standardise error responses with trace IDs for log correlation

## Non-Goals

- Logging all turns (only vetos are audited — APPROVE turns leave no DynamoDB record)
- Human-in-the-loop review (Phase 2 is automated only)
- Distributed rate limiting across multiple ECS tasks (single task in Phase 2; Redis backend added if scaled)

---

## Requirements

### Supervisor Agent

| ID | Requirement |
|----|-------------|
| SUP-01 | SupervisorAgent evaluates every Response Agent draft before it is sent to the user |
| SUP-02 | Model: `claude-haiku-4-5-20251001`, temperature=0, max_tokens=200 |
| SUP-03 | Output: structured JSON — decision (APPROVE/VETO), veto_reason, rule_category, confidence |
| SUP-04 | 7 veto categories: legal_advice, medical_advice, promise, pii_leak, social_engineering, hallucination, prompt_injection |
| SUP-05 | On VETO: send category-specific canned safe response to user |
| SUP-06 | On APPROVE: pass response to PII output scrubber, then send to user |
| SUP-07 | Supervisor uses the PII-scrubbed user query as input (not the raw query) |

### Audit Trail

| ID | Requirement |
|----|-------------|
| AUD-01 | Write audit record to DynamoDB `voicebot_safety_audits` on every VETO |
| AUD-02 | Audit record contains: session_id, turn_id, veto_reason, rule_category, supervisor_model, confidence, user_query_hash (SHA-256), response_hash (SHA-256), timestamp, HMAC signature |
| AUD-03 | Raw query and raw response text are never stored — only SHA-256 hashes |
| AUD-04 | Audit record is HMAC-SHA256 signed using key from env var `AUDIT_SIGNING_KEY` |
| AUD-05 | DynamoDB table TTL: 365 days |
| AUD-06 | APPROVE turns do not write any audit record |

### API Hardening

| ID | Requirement |
|----|-------------|
| API-01 | HTTP endpoints: 60 requests/minute per IP via slowapi |
| API-02 | WebSocket: 30 messages/minute per connection tracked in-memory |
| API-03 | Rate limit exceeded returns structured ErrorResponse with code RATE_LIMIT_EXCEEDED |
| API-04 | All error responses use standardised schema: code, message, trace_id, retryable, details |
| API-05 | trace_id is a UUID generated per-request, included in CloudWatch logs |

---

## Technical Design

### Supervisor Interface

```python
# backend/app/agents/supervisor.py

class SupervisorAgent:
    async def evaluate(
        self,
        user_query: str,          # PII-scrubbed
        proposed_response: str,
        session_id: str,
        turn_id: str,
    ) -> SupervisorDecision:
        ...

class SupervisorDecision(BaseModel):
    decision: Literal["APPROVE", "VETO"]
    veto_reason: str | None
    rule_category: str | None   # one of 7 categories or null
    confidence: float
```

### Canned Veto Responses

```python
VETO_RESPONSES = {
    "legal_advice":       "I'm not able to provide legal advice. Please contact Jackson County Legal Services.",
    "medical_advice":     "I'm not able to provide medical advice. Please contact a healthcare provider.",
    "promise":            "I can share county policy but cannot make commitments. Please contact the relevant department directly.",
    "pii_leak":           "I'm not able to share personal information about other individuals.",
    "social_engineering": "I'm not able to process that request.",
    "hallucination":      "I don't have enough information to answer that accurately. Please contact Jackson County directly.",
    "prompt_injection":   "I'm not able to process that request.",
    "default":            "I'm not able to help with that. Please contact Jackson County at the main line.",
}
```

### Audit Interface

```python
# backend/app/safety/audit.py

async def write_veto_audit(
    session_id: str,
    turn_id: str,
    user_query: str,        # hashed before storage
    proposed_response: str, # hashed before storage
    decision: SupervisorDecision,
    signing_key: bytes,
) -> None:
    ...
```

### DynamoDB Table Schema

| Attribute | Type | Description |
|-----------|------|-------------|
| session_id (PK) | String | WS session identifier |
| turn_id (SK) | String | UUID per turn |
| veto_reason | String | Supervisor explanation |
| rule_category | String | One of 7 categories |
| supervisor_model | String | Model ID used |
| confidence | String | Float as string |
| user_query_hash | String | SHA-256 of scrubbed query |
| response_hash | String | SHA-256 of draft response |
| timestamp | String | ISO 8601 UTC |
| signature | String | HMAC-SHA256 hex digest |
| ttl | Number | Unix epoch + 365 days |

---

## Acceptance Criteria

- [ ] SupervisorAgent returns VETO for "What are my legal rights to sue the county?"
- [ ] SupervisorAgent returns APPROVE for "What are the property tax payment deadlines?"
- [ ] VETO triggers DynamoDB write with all required fields
- [ ] Audit record signature verifiable: `hmac.compare_digest(recomputed, stored_signature)` passes
- [ ] Raw query text and raw response text are absent from DynamoDB record
- [ ] Rate limit test: 61st request in 1 minute returns 429 with RATE_LIMIT_EXCEEDED code
- [ ] All error responses contain a non-empty trace_id field
- [ ] Supervisor adds < 400ms p99 latency to turn pipeline

---

## Files

| File | Purpose |
|------|---------|
| `backend/app/agents/supervisor.py` | SupervisorAgent class |
| `backend/app/safety/audit.py` | Audit trail writer |
| `infra/scripts/setup_phase2_tables.py` | Creates voicebot_safety_audits table |
| `tests/unit/agents/test_supervisor.py` | Unit tests (mocked Haiku) |
| `tests/unit/safety/test_audit.py` | HMAC signing tests |
