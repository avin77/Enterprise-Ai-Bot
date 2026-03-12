# PRD: PII Scrubber — Plan 02-01

**Phase:** 02 — Public Sector Safety
**Status:** Planned
**Owner:** Engineering
**Date:** 2026-03-12

---

## Problem Statement

The voice bot currently stores and logs user queries verbatim. A user asking "My SSN is 123-45-6789, can I apply for a tax exemption?" would have their SSN written to DynamoDB, CloudWatch logs, and potentially included in LLM context. This is a compliance and privacy violation for a government-facing product.

---

## Goals

- Remove PII from user input before it reaches any storage or LLM call
- Remove PII from bot output before it is spoken to the user
- Log detection events (entity types only, not values) for compliance monitoring
- Add zero meaningful latency overhead to the turn pipeline

## Non-Goals

- Re-identification or reconstruction of scrubbed PII
- Storing scrubbed entity values in any form
- Language support beyond English (Phase 2 scope is English only)

---

## Requirements

### Functional

| ID | Requirement |
|----|-------------|
| PII-01 | Scrub input text before it is passed to the orchestrator pipeline |
| PII-02 | Scrub output text before it is sent to the TTS or WebSocket response |
| PII-03 | Detect and replace: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, US_DRIVER_LICENSE, US_PASSPORT, US_BANK_NUMBER, CREDIT_CARD, LOCATION |
| PII-04 | Replace detected entities with typed placeholders: e.g. `<US_SSN>`, `<PHONE_NUMBER>` |
| PII-05 | Return list of detected entity types (not values) alongside scrubbed text |
| PII-06 | Log detected entity types to CloudWatch as a structured event |
| PII-07 | Never log, store, or pass raw PII values to any downstream system |

### Non-Functional

| ID | Requirement |
|----|-------------|
| PII-NF-01 | p99 latency per scrub call: < 30ms on warm model |
| PII-NF-02 | Presidio models loaded at container startup (lifespan handler), not per-request |
| PII-NF-03 | Unit tests cover all 9 PII entity types with positive and negative examples |

---

## Technical Design

### Library

- `presidio-analyzer` + `presidio-anonymizer` (Microsoft open source)
- NLP backend: `spacy` with `en_core_web_sm` model

### Interface

```python
# backend/app/safety/pii.py

def scrub_input(text: str) -> tuple[str, list[str]]:
    """
    Scrub PII from user input.
    Returns (scrubbed_text, detected_entity_types).
    Called before orchestrator pipeline.
    """

def scrub_output(text: str) -> tuple[str, list[str]]:
    """
    Scrub PII from bot response.
    Returns (scrubbed_text, detected_entity_types).
    Called after Supervisor APPROVE, before sending to user.
    """

def preload_models() -> None:
    """
    Load Presidio + spaCy models into memory.
    Called once in FastAPI lifespan handler at startup.
    """
```

### Pipeline Integration Point

In `backend/app/orchestrator/pipeline.py`:
1. Call `scrub_input()` on user text before any processing
2. Call `scrub_output()` on Response Agent draft before returning to WebSocket handler

---

## Acceptance Criteria

- [ ] `scrub_input("My SSN is 123-45-6789")` returns `("My SSN is <US_SSN>", ["US_SSN"])`
- [ ] `scrub_input("Call me at 555-867-5309")` returns `("Call me at <PHONE_NUMBER>", ["PHONE_NUMBER"])`
- [ ] `scrub_input("How do I apply for a permit?")` returns unchanged text and empty entity list
- [ ] Output scrub applied on all APPROVE-path responses before WS send
- [ ] Detected entity types (not values) written to CloudWatch log on each scrub call that finds PII
- [ ] Container startup completes model loading within 5s
- [ ] All unit tests pass

---

## Files

| File | Purpose |
|------|---------|
| `backend/app/safety/pii.py` | Scrubber implementation |
| `tests/unit/safety/test_pii.py` | Unit tests |
| `requirements.txt` | Add presidio-analyzer, presidio-anonymizer, spacy |
