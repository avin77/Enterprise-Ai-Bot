---
status: testing
phase: 00-learning-mvp-bootstrap
source:
  - 00-01-SUMMARY.md
  - 00-02-SUMMARY.md
  - 00-03-SUMMARY.md
  - 00-04-SUMMARY.md
started: 2026-03-01T09:40:06Z
updated: 2026-03-01T09:40:06Z
---

## Current Test

number: 1
name: Health Endpoint Responds
expected: |
  Start the backend and send GET /health.
  You should get HTTP 200 with JSON containing status: "ok".
awaiting: user response

## Tests

### 1. Health Endpoint Responds
expected: GET /health returns HTTP 200 and status "ok".
result: [pending]

### 2. Chat Requires Auth Token
expected: POST /chat without a bearer token returns HTTP 401.
result: [pending]

### 3. Chat Roundtrip Works With Valid Token
expected: POST /chat with a valid bearer token returns HTTP 200 with reply formatted like assistant:<input>.
result: [pending]

### 4. Chat Rate Limit Is Enforced
expected: Repeated /chat calls above configured limit return HTTP 429.
result: [pending]

### 5. WebSocket Rejects Missing Token
expected: Connecting to /ws without a token is rejected.
result: [pending]

### 6. WebSocket Text Turn Works
expected: /ws with valid token sends ack, then a text message returns bot_text response with assistant:<input>.
result: [pending]

### 7. WebSocket Audio Turn Emits Pipeline Events
expected: /ws audio_chunk returns partial_text, bot_text, and bot_audio_chunk events in order.
result: [pending]

### 8. Frontend Uses Backend Endpoints Only
expected: Frontend sends requests only to backend /chat and /ws and contains no direct AWS SDK usage.
result: [pending]

### 9. AWS Bootstrap Assets Are Present
expected: backend Dockerfile, terraform files, and aws-bootstrap script exist and include expected ECR/ECS/bootstrap commands.
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0

## Gaps

[none yet]
