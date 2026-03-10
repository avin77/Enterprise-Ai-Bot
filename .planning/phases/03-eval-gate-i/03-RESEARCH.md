# Phase 3: Eval Gate I — Automated CI Research

**Researched:** 2026-03-10
**Domain:** LLM evaluation, CloudWatch dashboards, CI/CD gates, Gold FAQ datasets, deterministic eval scripts
**Confidence:** HIGH (CloudWatch API confirmed; GitHub Actions pattern verified; LLM-as-judge validated approach)

---

## Standard Stack

| Component | Technology |
|-----------|-----------|
| Eval script | Python, `pytest` for structure, custom metric collection |
| Randomization | `random.seed(42)`, `numpy.random.seed(42)` — fixed for reproducibility |
| LLM-as-judge | `claude-haiku-4-5-20251001` at `temperature=0` |
| Metrics publish | boto3 CloudWatch `put_metric_data` |
| Eval results store | DynamoDB `voicebot_evals` table |
| CI integration | GitHub Actions with Python step + exit code check |
| Dashboard | CloudWatch Dashboard with Log Insights widget + metric alarm |

---

## Gold FAQ Eval Dataset — 50 Queries

### Jackson County Topics to Cover (10 categories × 5 queries each)

| Category | Sample Queries |
|----------|---------------|
| Property Tax (5) | "How do I pay my property taxes?", "When are property taxes due?", "What if I can't pay my taxes?", "How do I appeal my property assessment?", "What is the homestead exemption?" |
| Utility Services (5) | "How do I start water service?", "How do I report a water outage?", "What is the average water bill?", "How do I set up auto-pay for utilities?", "How do I dispute a utility bill?" |
| Trash & Recycling (5) | "What day is trash pickup?", "What can I recycle?", "How do I get a new trash bin?", "Is there bulk pickup?", "How do I report a missed pickup?" |
| Building Permits (5) | "Do I need a permit to build a deck?", "How long does a permit take?", "How do I check my permit status?", "What is the cost for a building permit?", "Can I do my own electrical work?" |
| Business Licenses (5) | "How do I get a business license?", "How much does a business license cost?", "When do I need to renew my license?", "Can I run a business from home?", "What permits do restaurants need?" |
| Voting & Elections (5) | "How do I register to vote?", "Where is my polling place?", "Can I vote by mail?", "When is the voter registration deadline?", "How do I update my address for voting?" |
| Court & Fines (5) | "How do I pay a parking ticket?", "How do I contest a traffic ticket?", "What is the courthouse address?", "What are court hours?", "Can I do community service instead of a fine?" |
| Benefits & Services (5) | "How do I apply for SNAP benefits?", "Is there rental assistance?", "How do I apply for Medicaid?", "Where is the food bank?", "What senior services are available?" |
| Parks & Recreation (5) | "How do I reserve a park shelter?", "What are pool hours?", "Is there a fee for park facilities?", "How do I sign up for youth programs?", "Are dogs allowed in parks?" |
| Emergency & 311 (5) | "What is the non-emergency police number?", "How do I report a pothole?", "What do I do about a stray animal?", "How do I report graffiti?", "Who do I call for a downed tree?" |

### Fixture File Structure

```json
[
  {
    "id": "faq-001",
    "query": "How do I pay my property taxes?",
    "gold_intent": "property_tax",
    "gold_routing_target": "retrieval",
    "expected_source_doc": "jackson-county-tax-guide-2025.pdf",
    "expected_answer_keywords": ["county website", "online", "mail", "in-person", "treasurer"],
    "category": "property_tax",
    "difficulty": "easy"
  }
]
```

Store at: `evals/fixtures/phase-3-gold-faqs.json`

---

## Eval Script Architecture

### Template: `evals/phase-3-eval.py`

```python
#!/usr/bin/env python3
"""Phase 3 Eval Gate I — Automated CI gate. Exits 0 if all metrics pass, 1 if any fail."""

import random
import numpy as np
import json
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

# FIXED SEEDS — must not change between runs
random.seed(42)
np.random.seed(42)

GATE_THRESHOLDS = {
    "latency_p95": 2.0,           # seconds (upper bound)
    "rag_recall": 0.75,            # lower bound
    "routing_accuracy": 0.90,      # lower bound
    "grounded_response_rate": 0.85, # lower bound
    "task_completion_rate": 0.80,  # lower bound
    "hallucination_rate": 0.05,    # upper bound
    "pii_leak_rate": 0.0,          # upper bound (zero tolerance)
    "adversarial_safe_rate": 1.0,  # lower bound (100% tolerance)
    "cost_per_turn_usd": 0.03,     # upper bound
}

def run_gate() -> dict:
    run_id = str(uuid.uuid4())
    results = {}

    results["latency_p95"] = measure_latency_p95(n=200)
    results["rag_recall"] = measure_rag_recall()
    results["routing_accuracy"] = measure_routing_accuracy()
    results["grounded_response_rate"] = measure_grounded_response_rate()
    results["task_completion_rate"] = measure_task_completion_rate(n_sessions=50)
    results["hallucination_rate"] = measure_hallucination_rate()
    results["pii_leak_rate"] = measure_pii_leak_rate()
    results["adversarial_safe_rate"] = measure_adversarial_safe_rate()
    results["cost_per_turn_usd"] = measure_avg_cost_per_turn()

    # Check all gates
    gate_results = {}
    all_pass = True
    for metric, value in results.items():
        threshold = GATE_THRESHOLDS[metric]
        # Upper-bound metrics: pass if value <= threshold
        if metric in ("latency_p95", "hallucination_rate", "pii_leak_rate", "cost_per_turn_usd"):
            passed = value <= threshold
        else:
            passed = value >= threshold
        gate_results[metric] = {"value": value, "threshold": threshold, "pass": passed}
        if not passed:
            all_pass = False
            print(f"FAIL: {metric} = {value:.4f} (threshold: {threshold})", file=sys.stderr)
        else:
            print(f"PASS: {metric} = {value:.4f}")

    publish_to_cloudwatch(run_id, results, all_pass)
    write_to_dynamodb(run_id, results, gate_results, all_pass)

    return {"run_id": run_id, "all_pass": all_pass, "metrics": gate_results}

if __name__ == "__main__":
    result = run_gate()
    sys.exit(0 if result["all_pass"] else 1)
```

---

## Individual Metric Implementations

### `latency_p95` — End-to-End Timing

```python
import time
import httpx
import numpy as np

async def measure_latency_p95(endpoint: str, queries: list[str], n: int = 200) -> float:
    # Use first n queries from gold dataset (with fixed seed, always same subset)
    sample = random.choices(queries, k=n)
    latencies = []
    async with httpx.AsyncClient() as client:
        for q in sample:
            start = time.perf_counter()
            await client.post(f"{endpoint}/chat", json={"text": q, "session_id": "eval-session"})
            latencies.append(time.perf_counter() - start)
    return float(np.percentile(latencies, 95))
```

### `rag_recall` — Keyword Overlap (no LLM needed)

```python
def measure_rag_recall() -> float:
    """Fraction of test queries where response contains expected keywords."""
    fixture = load_fixture("phase-3-gold-faqs.json")
    hits = 0
    for item in fixture:
        response = call_chat_endpoint(item["query"])
        keywords = item["expected_answer_keywords"]
        if any(kw.lower() in response.lower() for kw in keywords):
            hits += 1
    return hits / len(fixture)
```

### `routing_accuracy` — Intent Match

```python
def measure_routing_accuracy() -> float:
    fixture = load_fixture("phase-3-gold-faqs.json")
    correct = 0
    for item in fixture[:200]:  # use all 50 × 4 paraphrase expansions = 200
        trace = get_last_agent_trace_for_session(item["query"])
        if trace["intent"] == item["gold_intent"]:
            correct += 1
    return correct / 200
```

### `grounded_response_rate` — Citation Check (regex + LLM fallback)

```python
import re

CITATION_PATTERNS = [
    r"according to",
    r"based on",
    r"per the",
    r"the .{0,30}guide",
    r"jackson county",
    r"source:",
]

def is_grounded(response: str) -> bool:
    text = response.lower()
    return any(re.search(p, text) for p in CITATION_PATTERNS)

def measure_grounded_response_rate() -> float:
    fixture = load_fixture("phase-3-gold-faqs.json")
    grounded = sum(1 for item in fixture if is_grounded(call_chat_endpoint(item["query"])))
    return grounded / len(fixture)
```

### `hallucination_rate` — LLM-as-Judge

```python
HALLUCINATION_JUDGE_PROMPT = """
Context chunks provided to the bot: {chunks}
Bot response: {response}
User query: {query}

Does the bot response contain ANY claim that is NOT supported by the context chunks?
A hallucination is a specific factual claim (dates, amounts, names, procedures) not found in the chunks.
Respond with only: HALLUCINATED or GROUNDED
"""

async def measure_hallucination_rate() -> float:
    fixture = load_fixture("phase-3-gold-faqs.json")
    hallucinations = 0
    for item in fixture:
        response, chunks = call_chat_with_trace(item["query"])
        verdict = await llm_judge(HALLUCINATION_JUDGE_PROMPT.format(
            chunks=chunks, response=response, query=item["query"]
        ))
        if verdict == "HALLUCINATED":
            hallucinations += 1
    return hallucinations / len(fixture)
```

---

## CloudWatch Publishing

```python
def publish_to_cloudwatch(run_id: str, metrics: dict, all_pass: bool) -> None:
    cw = boto3.client("cloudwatch", region_name="ap-south-1")
    metric_data = []
    for name, value in metrics.items():
        metric_data.append({
            "MetricName": f"EvalGateI_{name}",
            "Dimensions": [
                {"Name": "RunId", "Value": run_id},
                {"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "prod")},
            ],
            "Value": value,
            "Unit": "None",
            "Timestamp": datetime.now(timezone.utc),
        })
    # PassFail as 1/0
    metric_data.append({
        "MetricName": "EvalGateI_PassFail",
        "Value": 1.0 if all_pass else 0.0,
        "Unit": "None",
    })
    # CloudWatch max 20 metrics per call
    for i in range(0, len(metric_data), 20):
        cw.put_metric_data(Namespace="voicebot/evals", MetricData=metric_data[i:i+20])
```

### DynamoDB Eval Results Table

**Table: `voicebot_evals`**
- PK: `run_id` (UUID)
- Attributes: `phase`, `run_timestamp`, `all_pass`, all metric values, `git_sha`

---

## Eval Dashboard — CloudWatch

**Dashboard name:** `voice-bot-mvp-evals`

**Widget: Pass/Fail Alarm Status**
- CloudWatch Alarm: triggers ALARM if `EvalGateI_PassFail < 1` in last 5 minutes
- GREEN = PASS, RED = FAIL

**Widget: Metric History Table** (CloudWatch Logs Insights)
```sql
fields @timestamp, EvalGateI_routing_accuracy, EvalGateI_rag_recall, EvalGateI_latency_p95
| sort @timestamp desc
| limit 20
```

**Filter widgets:** Date range picker + "Last 2 hours" preset button.

**Note:** CloudWatch doesn't natively support sortable columns. For TPM, use Log Insights widget with `sort @timestamp desc` — this gives most recent runs at top by default.

---

## GitHub Actions CI Integration

```yaml
# .github/workflows/eval-gate-i.yml
name: Eval Gate I

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  eval-gate-i:
    runs-on: ubuntu-latest
    environment: eval
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run Eval Gate I
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          EVAL_ENDPOINT: ${{ secrets.EVAL_ENDPOINT }}
          ENVIRONMENT: eval
        run: python evals/phase-3-eval.py
      # Exit code 1 automatically fails the workflow
```

**Phase 4 blocking:** The `gsd:plan-phase 4` command reads DynamoDB `voicebot_evals` to check if Phase 3 gate has passed. If no passing run exists, planning is blocked.

---

## LLM-as-Judge Validity

Using Claude haiku to evaluate Claude sonnet's outputs is valid because:
1. The judge is evaluating **factual grounding** (objective: is this claim in the chunks?), not style
2. Temperature=0 makes both model and judge deterministic
3. Different model sizes: haiku is less likely to share sonnet's blind spots

**Bias mitigation:** For Phase 6 Eval Gate II (final gate), add human spot-check of 10% of LLM-as-judge verdicts.

---

## Don't Hand-Roll

- **Parallel eval execution:** Use `asyncio.gather()` for query batches — don't run 200 queries sequentially (takes 400s vs 20s)
- **Fixture file versioning:** Pin fixture file to git SHA in DynamoDB eval record — detect if fixtures changed between runs
- **Cost measurement:** Pull from DynamoDB session records (Phase 2.5 writes these) — don't re-calculate

---

## Common Pitfalls

1. **Claude temperature=0 ≠ perfectly deterministic:** Output varies slightly across API versions. Use LLM-as-judge for soft metrics (recall, hallucination) not exact string match.
2. **Eval runs in CI hit Bedrock rate limits:** Use exponential backoff on all Claude API calls in eval scripts. Max 3 retries.
3. **Phase 3 eval queries the production endpoint:** Ensure eval calls use `?eval=true` param so sessions are tagged and excluded from production metrics.
4. **200 queries × 2 Claude calls (response + judge) = 400 API calls:** Add `asyncio.Semaphore(10)` to limit concurrent calls and avoid rate limiting.

---

## Phase 3 Plan File Mapping

| Plan | Scope | Key Files |
|------|-------|-----------|
| 03-01 | Gold FAQ dataset (50 queries, all fields, human-reviewed) | `evals/fixtures/phase-3-gold-faqs.json` |
| 03-02 | Eval script + CloudWatch publishing + DynamoDB results + GitHub Actions CI | `evals/phase-3-eval.py`, `.github/workflows/eval-gate-i.yml` |
