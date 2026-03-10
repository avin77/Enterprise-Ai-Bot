# Phase 7: Reliability + Cost Hardening — Research

**Researched:** 2026-03-10
**Domain:** Circuit breakers, graceful degradation, spend caps, uptime verification, failure injection
**Confidence:** HIGH (pybreaker pattern confirmed; Fargate restart latency documented)

---

## Standard Stack

| Component | Technology |
|-----------|-----------|
| Circuit breaker | `pybreaker` (Python circuit breaker library) |
| Retry/backoff | `tenacity` |
| Graceful degradation | Custom fallback chain in FastAPI lifespan + dependency injection |
| Spend caps | DynamoDB session cost check + CloudWatch alarm |
| Synthetic monitoring | CloudWatch Synthetics canary |

---

## Circuit Breakers

### Dependencies Needing Circuit Breakers

| Dependency | Threshold | Recovery |
|-----------|-----------|----------|
| Redis | 5 failures in 30s → OPEN 60s | Fall back to direct BM25 (already in Phase 1) |
| DynamoDB | 5 failures in 60s → OPEN 120s | Fall back to in-memory session (no history) |
| Bedrock (Claude) | 3 failures in 30s → OPEN 30s | Return canned "I'm having trouble" response |
| Transcribe (ASR) | 3 failures in 60s → OPEN 60s | Fall back to text input mode (REL-02) |
| Polly (TTS) | 3 failures in 30s → OPEN 30s | Return text response via WebSocket (REL-02) |

### pybreaker Implementation

```python
import pybreaker

redis_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="redis",
    listeners=[CircuitBreakerMetricsListener()],  # publish to CloudWatch
)

dynamodb_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=120, name="dynamodb")
bedrock_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30, name="bedrock")
transcribe_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60, name="transcribe")
polly_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30, name="polly")

class CircuitBreakerMetricsListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        cw.put_metric_data(
            Namespace="voicebot/operations",
            MetricData=[{
                "MetricName": "CircuitBreakerOpen",
                "Dimensions": [{"Name": "Service", "Value": cb.name}],
                "Value": 1.0 if new_state.name == "open" else 0.0,
                "Unit": "None",
            }]
        )

# Usage:
@redis_breaker
def get_cached_result(query: str) -> str | None:
    return redis_client.get(query)
```

### Health Endpoint with Circuit Breaker State

```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "circuit_breakers": {
            "redis": redis_breaker.current_state.name,
            "dynamodb": dynamodb_breaker.current_state.name,
            "bedrock": bedrock_breaker.current_state.name,
            "transcribe": transcribe_breaker.current_state.name,
            "polly": polly_breaker.current_state.name,
        }
    }
```

---

## Graceful Degradation Chain

### Fallback Hierarchy

```
Normal path:
  Voice input → Transcribe → Agent pipeline → Polly → Voice output

If Transcribe fails (breaker OPEN):
  WebSocket sends {"type": "fallback_mode", "mode": "text"}
  Frontend switches to text input
  Text → Agent pipeline → Polly → Voice output (REL-02)

If Polly fails (breaker OPEN):
  Agent pipeline runs normally
  Response sent as text via WebSocket {"type": "text_response", "content": "..."}
  Frontend displays text (REL-02)

If Bedrock fails (breaker OPEN):
  Return canned response: "I'm having technical difficulties. Please try again shortly or contact Jackson County at [number]."

If Redis fails (breaker OPEN):
  Already handled in Phase 1: fall through to direct BM25

If DynamoDB fails (breaker OPEN):
  Continue turn with empty history (no multi-turn context)
  Write session record to Redis as backup (dequeue and flush when DynamoDB recovers)
```

### Text-Only Fallback (Frontend Contract)

WebSocket message protocol extension:
```json
{"type": "fallback_mode", "mode": "text_input", "reason": "asr_unavailable"}
{"type": "fallback_mode", "mode": "text_output", "reason": "tts_unavailable"}
```

Frontend listens for `fallback_mode` events and switches UI accordingly.

---

## Spend Caps (REL-03)

### Per-Session Cap Enforcement

```python
SESSION_COST_ALERT_USD = 0.50   # alert but don't block
SESSION_COST_HARD_CAP_USD = 1.00  # block further turns

async def check_session_cost_cap(session_id: str) -> bool:
    """Returns True if session can continue, False if capped."""
    session_total = await get_session_total_cost(session_id)  # sum from DynamoDB
    if session_total >= SESSION_COST_HARD_CAP_USD:
        logger.warning(f"Session {session_id} hit cost cap: ${session_total:.4f}")
        return False
    if session_total >= SESSION_COST_ALERT_USD:
        # Emit CloudWatch metric but don't block
        cw.put_metric_data(Namespace="voicebot/operations",
            MetricData=[{"MetricName": "SessionCostAlert", "Value": 1.0, "Unit": "Count"}])
    return True
```

**Response when capped:**
```python
COST_CAP_RESPONSE = "I've reached the session limit for this conversation. For additional help, please call Jackson County at [main number] or visit [website]."
```

### AWS Budgets Alarm

```python
budgets_client.create_budget(
    AccountId=AWS_ACCOUNT_ID,
    Budget={
        "BudgetName": "VoiceBot-Monthly",
        "BudgetLimit": {"Amount": "50", "Unit": "USD"},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
    },
    NotificationsWithSubscribers=[{
        "Notification": {
            "NotificationType": "ACTUAL",
            "ComparisonOperator": "GREATER_THAN",
            "Threshold": 80,  # alert at 80% of budget
        },
        "Subscribers": [{"SubscriptionType": "EMAIL", "Address": tpm_email}]
    }]
)
```

---

## Uptime Verification

### CloudWatch Synthetics Canary

```python
# canary/canary.py (deployed as Lambda by CloudWatch Synthetics)
import urllib3
import json

http = urllib3.PoolManager()

def handler(event, context):
    response = http.request("GET", "https://[ecs-alb]/health", timeout=5.0)
    if response.status != 200:
        raise Exception(f"Health check failed: {response.status}")
    data = json.loads(response.data)
    if data["status"] != "ok":
        raise Exception(f"Service unhealthy: {data}")
    # Check circuit breakers not all open
    open_breakers = [k for k, v in data["circuit_breakers"].items() if v == "open"]
    if len(open_breakers) >= 3:
        raise Exception(f"Multiple circuit breakers open: {open_breakers}")
```

Run every 1 minute. CloudWatch Synthetics reports uptime %. Target: 99.5% over 30-day window.

**ECS Fargate restart latency:** ~45-90 seconds for new task to be healthy (pull image + start + health check). Configure ECS health check grace period = 120 seconds.

---

## Failure Injection Tests

```python
# evals/phase-7-eval.py — failure injection test suite

async def test_redis_failure_fallback():
    """Kill Redis, verify BM25 still returns results."""
    kill_redis_container()
    response = await call_chat("What is trash pickup day?")
    assert response.status_code == 200
    assert len(response.json()["content"]) > 0, "Voice turn failed when Redis down"
    restore_redis_container()

async def test_tts_failure_fallback():
    """Simulate Polly failure, verify text response returned."""
    with mock.patch("app.services.tts.synthesize", side_effect=Exception("Polly unavailable")):
        ws_messages = await collect_ws_messages("Tell me about permits")
        text_msgs = [m for m in ws_messages if m["type"] == "text_response"]
        assert len(text_msgs) > 0, "No text fallback when TTS failed"

async def test_cost_cap_enforcement():
    """Inject high session cost, verify cap blocks further turns."""
    session_id = "test-cap-session"
    await set_session_cost(session_id, 1.01)  # above hard cap
    response = await call_chat("Hello", session_id=session_id)
    assert COST_CAP_RESPONSE in response.json()["content"]
```

---

## Phase 7 Plan File Mapping

| Plan | Scope | Key Files |
|------|-------|-----------|
| 07-01 | Circuit breakers (pybreaker, all 5 dependencies) + graceful degradation (text fallback) | `backend/app/resilience/circuit_breakers.py`, `backend/app/resilience/fallbacks.py` |
| 07-02 | Spend caps (per-session check, AWS Budgets alarm) + synthetic monitoring canary | `backend/app/billing/cost_cap.py`, `canary/canary.py` |
| 07-03 | Reliability eval: failure injection tests + uptime verification | `evals/phase-7-eval.py` |
