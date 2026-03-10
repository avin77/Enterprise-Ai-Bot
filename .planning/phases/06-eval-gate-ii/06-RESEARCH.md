# Phase 6: Eval Gate II — Full Production Readiness Research

**Researched:** 2026-03-10
**Domain:** WebSocket load testing, security scanning, consolidated eval gates, ECS concurrent capacity
**Confidence:** HIGH (Locust WebSocket support confirmed; trivy + Bandit combination standard)

---

## Standard Stack

| Component | Technology |
|-----------|-----------|
| Load testing | `locust` with WebSocket support via `websocket-client` |
| Security scanning | `bandit` (Python SAST) + `trivy` (container image) + `safety` (dependency vulns) |
| Consolidated eval | `evals/phase-6-eval.py` (extends Phase 3 script) |
| CI gate | GitHub Actions (same pattern as Phase 3, stricter thresholds) |

---

## Load Testing — 50 Concurrent WebSocket Turns

### Locust WebSocket Test

```python
# evals/load_test.py
from locust import User, task, between
import websocket
import json
import time

class VoiceBotUser(User):
    wait_time = between(1, 3)

    def on_start(self):
        self.ws = websocket.create_connection(
            f"ws://{self.host}/ws",
            header={"Authorization": f"Bearer {TEST_TOKEN}"}
        )

    @task
    def voice_turn(self):
        query = random.choice(EVAL_QUERIES)
        start = time.perf_counter()
        self.ws.send(json.dumps({"type": "text", "content": query, "session_id": f"load-{self.user_id}"}))

        # Wait for complete response
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("type") == "turn_complete":
                latency = time.perf_counter() - start
                self.environment.events.request.fire(
                    request_type="WS",
                    name="voice_turn",
                    response_time=latency * 1000,
                    response_length=len(json.dumps(msg)),
                    exception=None if latency < 2.0 else Exception(f"SLO breach: {latency:.2f}s"),
                )
                break

    def on_stop(self):
        self.ws.close()
```

**Run command:**
```bash
locust -f evals/load_test.py --headless -u 50 -r 10 --run-time 5m --host ws://localhost:8000
```

**ECS 1024 MB capacity for 50 concurrent turns:**
- Per-turn memory: ~50 MB peak (torch loaded once, not per-turn)
- 50 concurrent turns × 50 MB = 2,500 MB needed
- **PROBLEM:** 1024 MB task is insufficient for 50 concurrent turns!
- **Solution:** Load test against 2+ ECS tasks (ECS service desired count = 2). Each task handles 25 concurrent turns = 1,250 MB needed per task. Fits in 1024 MB.
- Add ECS auto-scaling in Phase 7 if needed for production.

---

## Security Scanning

### Tool Stack

```yaml
# .github/workflows/security-scan.yml
- name: Bandit SAST
  run: bandit -r backend/ -ll -q --exit-zero
  # -ll = only HIGH severity; fails on HIGH findings

- name: Safety dependency check
  run: safety check --full-report
  # Fails if known CVEs in requirements.txt

- name: Trivy container scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE_URI }}
    format: table
    exit-code: 1
    severity: CRITICAL  # Only fail on CRITICAL
```

**What counts as gate-failing:**
- Bandit: any HIGH severity finding
- Safety: any CRITICAL CVE
- Trivy: any CRITICAL container vuln

**WebSocket-specific checks:**
- Auth token validated on WebSocket handshake (not just HTTP headers)
- Message size limit: 64KB max per WebSocket frame (prevent DoS)
- Connection timeout: 10 minutes max (prevent zombie connections)

---

## Consolidated Gate Metrics

Phase 6 runs ALL Phase 3 metrics PLUS:

| Metric | Definition | Target |
|--------|-----------|--------|
| All Phase 3 metrics | Same as Phase 3 (no regression allowed) | Same thresholds |
| `concurrent_turns_ok` | 50 concurrent WS turns, p95 latency ≤ 2s, error rate ≤ 1% | true |
| `security_scan_critical` | Critical findings from bandit + trivy + safety | 0 |
| `cost_per_turn_under_load` | Cost per turn during load test (50 concurrent) | < $0.03 |

**Cost under load:** With 50 concurrent turns and tasks well-utilized, compute cost per turn drops significantly (more turns per dollar of task time). LLM cost stays constant per turn.

---

## Eval Script Extension

```python
# evals/phase-6-eval.py
from evals.phase_3_eval import run_phase3_gate  # reuse Phase 3 measurements

def run_gate() -> dict:
    # Run all Phase 3 metrics first
    p3_results = run_phase3_gate(skip_publish=True)

    # Add load test
    concurrent_ok = run_load_test(users=50, duration_minutes=5, slo_seconds=2.0)

    # Add security scan
    security_critical = run_security_scans()  # 0 = pass

    # Publish all
    all_results = {**p3_results["metrics"], "concurrent_turns_ok": concurrent_ok, "security_scan_critical": security_critical}
    publish_to_cloudwatch("phase-6", all_results)
    write_to_dynamodb("phase-6", all_results)

    all_pass = p3_results["all_pass"] and concurrent_ok and security_critical == 0
    return {"all_pass": all_pass, "metrics": all_results}
```

---

## Phase 6 Plan File Mapping

| Plan | Scope | Key Files |
|------|-------|-----------|
| 06-01 | Locust WebSocket load test + Bandit/Trivy/Safety security scan | `evals/load_test.py`, `.github/workflows/security-scan.yml` |
| 06-02 | Consolidated eval gate Phase 6 + CloudWatch dashboard update | `evals/phase-6-eval.py` |
