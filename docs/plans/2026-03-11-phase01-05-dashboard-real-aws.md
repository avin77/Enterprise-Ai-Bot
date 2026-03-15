# Phase 01-05: Local Dashboard with Real AWS Data

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the local observability dashboard to display real DynamoDB/CloudWatch data when `USE_AWS_MOCKS=false`, while keeping mock fallback for local development.

**Architecture:** Dashboard serves `frontend/pages/dashboard.html` from FastAPI. New `/api/*` endpoints in `main.py` proxy to real DynamoDB (`voicebot_faqs`, `voicebot_sessions`) and CloudWatch (`voicebot/latency` namespace) via boto3 when mocks are disabled. When `USE_AWS_MOCKS=true` (default), returns in-memory mock data so development needs no AWS credentials.

**Tech Stack:** FastAPI, boto3, DynamoDB, CloudWatch, vanilla JS (polling every 2s), Python 3.11

---

## Task 1: Add `/api/knowledge-stats` Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `tests/backend/test_dashboard_api.py` (create)

**Step 1: Write failing test**

```python
# tests/backend/test_dashboard_api.py
import pytest
from fastapi.testclient import TestClient
import os

os.environ["USE_AWS_MOCKS"] = "true"

from backend.app.main import app

client = TestClient(app)

def test_knowledge_stats_returns_shape():
    resp = client.get("/api/knowledge-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_chunks" in data
    assert "total_documents" in data
    assert "last_ingested" in data
    assert isinstance(data["total_chunks"], int)
```

**Step 2: Run to verify it fails**

```bash
cd C:\Coding\Enterprise-AI-Voice-Bot
pytest tests/backend/test_dashboard_api.py::test_knowledge_stats_returns_shape -v
```
Expected: `FAILED` — 404 Not Found (endpoint doesn't exist yet)

**Step 3: Implement endpoint in `backend/app/main.py`**

Add after the existing `/metrics` endpoint:

```python
@app.get("/api/knowledge-stats")
async def knowledge_stats() -> dict:
    """FAQ knowledge base stats — real DynamoDB or mock."""
    if _USE_MOCKS:
        return {
            "total_chunks": 12,
            "total_documents": 3,
            "last_ingested": "2026-03-11T00:00:00Z",
            "source": "mock",
        }
    try:
        resp = _dynamo_client.scan(
            TableName="voicebot_faqs",
            Select="COUNT",
        )
        # Get unique document names via a second scan (small table in MVP)
        items_resp = _dynamo_client.scan(
            TableName="voicebot_faqs",
            ProjectionExpression="source_doc",
        )
        docs = {item["source_doc"]["S"] for item in items_resp.get("Items", [])}
        return {
            "total_chunks": resp["Count"],
            "total_documents": len(docs),
            "last_ingested": None,  # populated in Phase 4
            "source": "dynamodb",
        }
    except Exception as e:
        logger.warning(f"knowledge-stats DynamoDB error: {e}")
        return {"total_chunks": 0, "total_documents": 0, "last_ingested": None, "source": "error"}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_dashboard_api.py::test_knowledge_stats_returns_shape -v
```
Expected: `PASSED`

**Step 5: Commit**

```bash
git add backend/app/main.py tests/backend/test_dashboard_api.py
git commit -m "feat(01-05): add /api/knowledge-stats endpoint — real DynamoDB + mock fallback"
```

---

## Task 2: Add `/api/session-stats` Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `tests/backend/test_dashboard_api.py`

**Step 1: Write failing test**

```python
# Add to tests/backend/test_dashboard_api.py
def test_session_stats_returns_shape():
    resp = client.get("/api/session-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_sessions" in data
    assert "total_turns" in data
    assert "slo_met_pct" in data
    assert 0.0 <= data["slo_met_pct"] <= 100.0
```

**Step 2: Run to verify it fails**

```bash
pytest tests/backend/test_dashboard_api.py::test_session_stats_returns_shape -v
```
Expected: `FAILED` — 404

**Step 3: Implement in `backend/app/main.py`**

```python
@app.get("/api/session-stats")
async def session_stats() -> dict:
    """Conversation session summary — real DynamoDB or mock."""
    if _USE_MOCKS:
        return {
            "active_sessions": 2,
            "total_turns": 8,
            "slo_met_pct": 87.5,
            "source": "mock",
        }
    try:
        resp = _dynamo_client.scan(TableName="voicebot_sessions")
        items = resp.get("Items", [])
        total_turns = sum(int(i.get("turn_number", {}).get("N", 0)) for i in items)
        slo_met = sum(1 for i in items if i.get("slo_met", {}).get("BOOL", False))
        pct = round((slo_met / total_turns * 100) if total_turns else 0.0, 1)
        return {
            "active_sessions": len(items),
            "total_turns": total_turns,
            "slo_met_pct": pct,
            "source": "dynamodb",
        }
    except Exception as e:
        logger.warning(f"session-stats DynamoDB error: {e}")
        return {"active_sessions": 0, "total_turns": 0, "slo_met_pct": 0.0, "source": "error"}
```

**Step 4: Run test**

```bash
pytest tests/backend/test_dashboard_api.py::test_session_stats_returns_shape -v
```
Expected: `PASSED`

**Step 5: Commit**

```bash
git add backend/app/main.py tests/backend/test_dashboard_api.py
git commit -m "feat(01-05): add /api/session-stats endpoint — real DynamoDB + mock fallback"
```

---

## Task 3: Add `/api/cloudwatch-latency` Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `tests/backend/test_dashboard_api.py`

**Step 1: Write failing test**

```python
# Add to tests/backend/test_dashboard_api.py
def test_cloudwatch_latency_returns_shape():
    resp = client.get("/api/cloudwatch-latency")
    assert resp.status_code == 200
    data = resp.json()
    assert "p50_ms" in data
    assert "p95_ms" in data
    assert "source" in data
```

**Step 2: Run to verify it fails**

```bash
pytest tests/backend/test_dashboard_api.py::test_cloudwatch_latency_returns_shape -v
```
Expected: `FAILED` — 404

**Step 3: Implement in `backend/app/main.py`**

```python
@app.get("/api/cloudwatch-latency")
async def cloudwatch_latency() -> dict:
    """Recent p50/p95 turn latency — CloudWatch or in-memory buffer fallback."""
    # Always try in-memory buffer first (fastest, no AWS call)
    buf = get_latency_buffer()
    pcts = buf.all_percentiles()
    total = pcts.get("total", {})
    if total.get("p50") is not None:
        return {
            "p50_ms": total["p50"],
            "p95_ms": total["p95"],
            "p99_ms": total["p99"],
            "sample_count": total.get("count", 0),
            "source": "in-memory",
        }
    # Fallback: CloudWatch (real mode only, last 1 hour)
    if not _USE_MOCKS and _dynamo_client is not None:
        try:
            import boto3, datetime
            cw = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "ap-south-1"))
            now = datetime.datetime.utcnow()
            resp = cw.get_metric_statistics(
                Namespace="voicebot/latency",
                MetricName="TotalTurnLatency",
                StartTime=now - datetime.timedelta(hours=1),
                EndTime=now,
                Period=3600,
                Statistics=["Average"],
            )
            pts = resp.get("Datapoints", [])
            avg = pts[0]["Average"] if pts else None
            return {"p50_ms": avg, "p95_ms": None, "p99_ms": None, "sample_count": len(pts), "source": "cloudwatch"}
        except Exception as e:
            logger.warning(f"cloudwatch-latency error: {e}")
    return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "sample_count": 0, "source": "no-data"}
```

**Step 4: Run test**

```bash
pytest tests/backend/test_dashboard_api.py::test_cloudwatch_latency_returns_shape -v
```
Expected: `PASSED`

**Step 5: Commit**

```bash
git add backend/app/main.py tests/backend/test_dashboard_api.py
git commit -m "feat(01-05): add /api/cloudwatch-latency endpoint — buffer-first, CW fallback"
```

---

## Task 4: Build Dashboard HTML with Real Data Sections

**Files:**
- Create: `frontend/pages/dashboard.html`
- Create: `frontend/js/dashboard.js`

**Step 1: Create `frontend/pages/dashboard.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Voice Bot Dashboard</title>
  <style>
    body { font-family: monospace; background: #0d1117; color: #c9d1d9; margin: 0; padding: 16px; }
    h1 { color: #58a6ff; font-size: 1.2rem; margin-bottom: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px; }
    .card h2 { font-size: 0.85rem; color: #8b949e; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 1px; }
    .metric { font-size: 2rem; font-weight: bold; color: #58a6ff; }
    .sub { font-size: 0.75rem; color: #8b949e; margin-top: 4px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; }
    .green { background: #1f4a1f; color: #3fb950; }
    .yellow { background: #3d3000; color: #d29922; }
    .red { background: #3d1010; color: #f85149; }
    .source { font-size: 0.65rem; color: #484f58; margin-top: 8px; }
    #status { font-size: 0.7rem; color: #484f58; margin-bottom: 12px; }
  </style>
</head>
<body>
  <h1>Voice Bot — Observability Dashboard</h1>
  <div id="status">Connecting...</div>
  <div class="grid">
    <div class="card">
      <h2>Knowledge Base</h2>
      <div class="metric" id="kb-chunks">—</div>
      <div class="sub">FAQ chunks in DynamoDB</div>
      <div class="sub" id="kb-docs">— source documents</div>
      <div class="source" id="kb-source"></div>
    </div>
    <div class="card">
      <h2>Sessions</h2>
      <div class="metric" id="sess-count">—</div>
      <div class="sub">Active sessions</div>
      <div class="sub" id="sess-turns">— total turns</div>
      <div class="sub" id="sess-slo"></div>
      <div class="source" id="sess-source"></div>
    </div>
    <div class="card">
      <h2>Turn Latency</h2>
      <div class="metric" id="lat-p50">—</div>
      <div class="sub">p50 (ms)</div>
      <div class="sub" id="lat-p95">p95: —ms</div>
      <div class="sub" id="lat-p99">p99: —ms</div>
      <div class="source" id="lat-source"></div>
    </div>
    <div class="card">
      <h2>Pipeline Metrics (local buffer)</h2>
      <div id="pipeline-stages">Loading...</div>
      <div class="source">source: in-memory buffer</div>
    </div>
  </div>
  <script src="/static/js/dashboard.js"></script>
</body>
</html>
```

**Step 2: Create `frontend/js/dashboard.js`**

```javascript
// Poll all dashboard endpoints every 2 seconds
const REFRESH_MS = 2000;

function colorLatency(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 500) return 'green';
  if (ms < 1500) return 'yellow';
  return 'red';
}

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url} → ${resp.status}`);
  return resp.json();
}

async function updateKnowledge() {
  const data = await fetchJSON('/api/knowledge-stats');
  document.getElementById('kb-chunks').textContent = data.total_chunks;
  document.getElementById('kb-docs').textContent = `${data.total_documents} source documents`;
  document.getElementById('kb-source').textContent = `source: ${data.source}`;
}

async function updateSessions() {
  const data = await fetchJSON('/api/session-stats');
  document.getElementById('sess-count').textContent = data.active_sessions;
  document.getElementById('sess-turns').textContent = `${data.total_turns} total turns`;
  const slo = document.getElementById('sess-slo');
  slo.textContent = `SLO met: ${data.slo_met_pct}%`;
  slo.className = `sub badge ${data.slo_met_pct >= 95 ? 'green' : data.slo_met_pct >= 80 ? 'yellow' : 'red'}`;
  document.getElementById('sess-source').textContent = `source: ${data.source}`;
}

async function updateLatency() {
  const data = await fetchJSON('/api/cloudwatch-latency');
  const p50 = data.p50_ms !== null ? Math.round(data.p50_ms) : '—';
  document.getElementById('lat-p50').textContent = p50 !== '—' ? `${p50}ms` : '—';
  document.getElementById('lat-p95').textContent = `p95: ${data.p95_ms !== null ? Math.round(data.p95_ms) + 'ms' : '—'}`;
  document.getElementById('lat-p99').textContent = `p99: ${data.p99_ms !== null ? Math.round(data.p99_ms) + 'ms' : '—'}`;
  document.getElementById('lat-source').textContent = `source: ${data.source} (${data.sample_count} samples)`;
}

async function updatePipeline() {
  const data = await fetchJSON('/metrics');
  const stages = ['asr', 'rag', 'llm', 'tts', 'total'];
  const el = document.getElementById('pipeline-stages');
  el.innerHTML = stages.map(stage => {
    const s = data[stage] || {};
    const p50 = s.p50 !== undefined ? `${Math.round(s.p50)}ms` : '—';
    const p95 = s.p95 !== undefined ? `${Math.round(s.p95)}ms` : '—';
    const cls = colorLatency(s.p50);
    return `<div style="margin-bottom:4px"><span class="badge ${cls}">${stage.toUpperCase()}</span> p50: ${p50} p95: ${p95}</div>`;
  }).join('');
}

async function refresh() {
  const statusEl = document.getElementById('status');
  try {
    await Promise.all([updateKnowledge(), updateSessions(), updateLatency(), updatePipeline()]);
    statusEl.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
```

**Step 3: Serve static files from FastAPI — add to `backend/app/main.py`**

Add after `app = FastAPI(...)`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

_FRONTEND_DIR = pathlib.Path(__file__).parent.parent.parent / "frontend"

# Mount static JS
if (_FRONTEND_DIR / "js").exists():
    app.mount("/static/js", StaticFiles(directory=str(_FRONTEND_DIR / "js")), name="static-js")

@app.get("/dashboard")
async def dashboard():
    return FileResponse(str(_FRONTEND_DIR / "pages" / "dashboard.html"))
```

**Step 4: Create `frontend/` directories**

```bash
mkdir -p frontend/pages frontend/js
```

**Step 5: Write a smoke test for dashboard route**

```python
# Add to tests/backend/test_dashboard_api.py
def test_dashboard_page_loads():
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Voice Bot" in resp.content
```

**Step 6: Run all dashboard tests**

```bash
pytest tests/backend/test_dashboard_api.py -v
```
Expected: 4 tests `PASSED`

**Step 7: Commit**

```bash
git add frontend/ backend/app/main.py tests/backend/test_dashboard_api.py
git commit -m "feat(01-05): dashboard HTML/JS + /dashboard route serving real AWS data"
```

---

## Task 5: Manual Verification

**Step 1: Start server in mock mode (no AWS needed)**

```bash
USE_AWS_MOCKS=true uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000/dashboard` — should show mock data (12 chunks, 2 sessions, etc.)

**Step 2: Start server in real AWS mode**

```bash
USE_AWS_MOCKS=false AWS_REGION=ap-south-1 uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000/dashboard` — shows real DynamoDB data (0 chunks until PDFs ingested in 01-06)

**Step 3: Verify `/api/knowledge-stats` directly**

```bash
curl http://localhost:8000/api/knowledge-stats
curl http://localhost:8000/api/session-stats
curl http://localhost:8000/api/cloudwatch-latency
```

**Step 4: Commit any fixes, then run full test suite**

```bash
pytest tests/backend/ -v
```

---

## Success Criteria

- [ ] `GET /dashboard` serves dashboard HTML
- [ ] `GET /api/knowledge-stats` returns `{total_chunks, total_documents, source}`
- [ ] `GET /api/session-stats` returns `{active_sessions, total_turns, slo_met_pct, source}`
- [ ] `GET /api/cloudwatch-latency` returns `{p50_ms, p95_ms, source}`
- [ ] With `USE_AWS_MOCKS=true`: all endpoints return mock data, no AWS calls
- [ ] With `USE_AWS_MOCKS=false`: endpoints query real DynamoDB/CW (graceful error if empty)
- [ ] Dashboard auto-refreshes every 2 seconds
- [ ] All 4 dashboard API tests pass
