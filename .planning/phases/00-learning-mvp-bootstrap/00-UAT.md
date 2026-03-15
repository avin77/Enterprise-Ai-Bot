---
status: testing
phase: 00-learning-mvp-bootstrap
source:
  - 00-01-SUMMARY.md
  - 00-02-SUMMARY.md
  - 00-03-SUMMARY.md
  - 00-04-SUMMARY.md
  - 00-05-SUMMARY.md
started: 2026-03-01T09:40:06Z
updated: 2026-03-05T00:00:00Z
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
expected: backend Dockerfile and aws-bootstrap script exist and include expected AWS CLI ECR/ECS deploy and teardown commands.
result: [pending]

### 10. AWS CLI Deploy/Teardown Smoke Flow
expected: |
  Run aws-bootstrap script in deploy mode with ECS networking inputs, validate /health via PHASE0_SMOKE_URL,
  then run teardown mode and confirm ECS service no longer exists.
result: [pending]

## Summary

total: 10
passed: 0
issues: 0
pending: 10
skipped: 0

## Gaps

[none yet]
