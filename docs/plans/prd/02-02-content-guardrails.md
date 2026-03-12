# PRD: Content Guardrails — Plan 02-02

**Phase:** 02 — Public Sector Safety
**Status:** Planned
**Owner:** Engineering
**Date:** 2026-03-12

---

## Problem Statement

The Response Agent currently has no explicit prohibitions. It will attempt to answer any question grounded in retrieved context, including questions that touch legal interpretation, medical advice, or county commitments. This creates liability exposure for Jackson County and potential user harm from authoritative-sounding but incorrect guidance.

---

## Goals

- Prevent the Response Agent from producing legally or medically advisory content
- Prevent the bot from making promises on behalf of the county
- Provide helpful, standardised redirect responses when content is prohibited
- Make the guardrail rules auditable and version-controlled (in code, not buried in a dashboard)

## Non-Goals

- Blocking all mentions of legal or medical topics — the bot should be able to say "contact Legal Services at X"
- Replacing the Supervisor Agent — guardrails are a first-pass prompt-level defence; the Supervisor is the second-pass AI reviewer
- Filtering retrieval results (that is a Phase 4 concern)

---

## Requirements

### Functional

| ID | Requirement |
|----|-------------|
| GRD-01 | Inject prohibited content rules into the Response Agent system prompt on every call |
| GRD-02 | Define 5 prohibited categories: legal_advice, medical_advice, financial_advice, county_promise, third_party_pii |
| GRD-03 | Each category includes: description of what is prohibited, example of a prohibited response, safe redirect language |
| GRD-04 | Safe redirect language references real Jackson County contact points (Legal Services, main number, etc.) |
| GRD-05 | Guardrail rules are defined as a Python constant in `guardrails.py` — not hardcoded in prompt strings scattered across files |
| GRD-06 | The system prompt injection is composable: `build_response_system_prompt(base_prompt, guardrail_rules)` |

### Non-Functional

| ID | Requirement |
|----|-------------|
| GRD-NF-01 | Zero added latency — rules are injected as a string, not an API call |
| GRD-NF-02 | Unit tests assert that the injected system prompt contains each prohibited category |
| GRD-NF-03 | Rules must be reviewable and editable by a non-engineer (plain English in the constant) |

---

## Technical Design

### Prohibited Categories

```python
# backend/app/safety/guardrails.py

GUARDRAIL_RULES = """
PROHIBITED CONTENT — never provide the following:

1. LEGAL ADVICE: Do not interpret laws, assess legal liability, predict legal outcomes,
   or recommend legal action. If asked, say:
   "For legal questions, please contact Jackson County Legal Services at [number]."

2. MEDICAL ADVICE: Do not diagnose conditions, recommend treatments, or interpret
   symptoms. If asked, say:
   "For medical questions, please contact a healthcare provider or call 911 for emergencies."

3. FINANCIAL ADVICE: Do not recommend investments, financial products, or financial
   decisions. You may state factual fee amounts from official documents.

4. COUNTY PROMISES: Do not commit to specific actions, timelines, or outcomes on behalf
   of Jackson County. If asked, say:
   "I can share the policy, but for specific commitments please contact [department] directly."

5. THIRD-PARTY PERSONAL INFORMATION: Do not look up, speculate about, or share any
   information about specific residents, account holders, or other individuals.
"""
```

### Interface

```python
def build_response_system_prompt(base_prompt: str) -> str:
    """
    Append guardrail rules to the Response Agent base system prompt.
    Called in llm.py before every Response Agent message create call.
    """
```

### Integration Point

In `backend/app/services/llm.py`, the Response Agent `system=` parameter is built via `build_response_system_prompt(base)` on every call.

---

## Acceptance Criteria

- [ ] Response Agent system prompt contains all 5 prohibited categories on every call
- [ ] Integration test: query "Should I sue the county?" returns a legal services redirect, not legal analysis
- [ ] Integration test: query "I have chest pain, what should I do?" returns healthcare provider redirect
- [ ] `build_response_system_prompt()` unit test asserts all 5 category keywords appear in output
- [ ] Guardrail rules constant is in one place only (`guardrails.py`) — no duplication in other files

---

## Files

| File | Purpose |
|------|---------|
| `backend/app/safety/guardrails.py` | Rules constant + prompt builder |
| `tests/unit/safety/test_guardrails.py` | Unit tests |
