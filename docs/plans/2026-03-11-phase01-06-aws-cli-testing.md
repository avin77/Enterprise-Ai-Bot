# Phase 01-06: AWS CLI Testing Workflow (50-Turn Test + Cost Validation)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide a complete workflow to ingest 5 PDFs into real AWS (S3 + DynamoDB with embeddings), run 50 test voice turns via the ECS API, and verify cost + latency using AWS CLI commands.

**Architecture:**
- `knowledge/pipeline/ingest.py` (existing text extractor) extended with `run_ingest.py` CLI wrapper that generates embeddings via `all-MiniLM-L6-v2` and writes to DynamoDB + S3
- `tests/e2e/run_50_turns.py` WebSocket test script sends 50 predefined government questions and records per-turn latency + cost
- `docs/AWS-CLI-TESTING-GUIDE.md` provides copy-paste AWS CLI commands to verify everything from terminal

**Tech Stack:** Python, boto3, sentence-transformers (`all-MiniLM-L6-v2`), pdfplumber, websockets, AWS CLI (already installed), DynamoDB, S3, CloudWatch, ECS

**Prerequisites:**
- AWS CLI configured: `aws configure` (region: ap-south-1, account: 148952810686)
- ECS task running: `http://65.0.116.5:8000`
- `pip install sentence-transformers pdfplumber boto3 websockets`

---

## Task 1: Extend Ingest Pipeline with S3 Upload + DynamoDB Write + Embeddings

**Files:**
- Create: `knowledge/pipeline/run_ingest.py` (CLI wrapper)
- Create: `tests/knowledge/test_ingest_pipeline.py`
- Modify: `knowledge/pipeline/ingest.py` (already has `extract_chunks_from_pdf`)

**What this does:**
1. Reads PDF from `data/pdfs/`
2. Extracts chunks (existing `extract_chunks_from_pdf`)
3. Generates 384-dim embedding per chunk (all-MiniLM-L6-v2)
4. Uploads PDF to S3 bucket
5. Writes each chunk + embedding to DynamoDB `voicebot_faqs` table

**Step 1: Write failing test**

```python
# tests/knowledge/test_ingest_pipeline.py
import pytest
from unittest.mock import patch, MagicMock
from knowledge.pipeline.run_ingest import build_dynamo_item, generate_embedding

def test_build_dynamo_item_has_required_fields():
    chunk = {
        "text": "County permits require form A12.",
        "source_doc": "permits.pdf",
        "chunk_id": "permits.pdf:chunk:0",
        "department": "planning",
        "page_ref": None,
    }
    embedding = [0.1] * 384
    item = build_dynamo_item(chunk, embedding)
    assert item["chunk_id"]["S"] == "permits.pdf:chunk:0"
    assert item["text"]["S"] == chunk["text"]
    assert item["source_doc"]["S"] == "permits.pdf"
    assert item["department"]["S"] == "planning"
    assert "embedding" in item  # binary field
    assert "created_at" in item

def test_generate_embedding_returns_384_dims():
    vec = generate_embedding("test sentence about county permits")
    assert len(vec) == 384
    assert all(isinstance(v, float) for v in vec)
```

**Step 2: Run to verify it fails**

```bash
pytest tests/knowledge/test_ingest_pipeline.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: knowledge.pipeline.run_ingest`

**Step 3: Create `knowledge/pipeline/run_ingest.py`**

```python
"""
knowledge/pipeline/run_ingest.py
CLI: python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/ --table voicebot_faqs --bucket voicebot-mvp-docs

Ingest PDFs → extract chunks → generate embeddings → write to DynamoDB + upload to S3.
"""
from __future__ import annotations
import argparse
import datetime
import os
import struct
import boto3
from pathlib import Path
from knowledge.pipeline.ingest import extract_chunks_from_pdf

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate 384-dim embedding using all-MiniLM-L6-v2."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _floats_to_bytes(floats: list[float]) -> bytes:
    """Pack float list as little-endian 32-bit floats (DynamoDB Binary)."""
    return struct.pack(f"<{len(floats)}f", *floats)


def build_dynamo_item(chunk: dict, embedding: list[float]) -> dict:
    """Build DynamoDB PutItem-ready dict for a FAQ chunk."""
    return {
        "chunk_id": {"S": chunk["chunk_id"]},
        "text": {"S": chunk["text"]},
        "source_doc": {"S": chunk["source_doc"]},
        "department": {"S": chunk["department"]},
        "page_ref": {"S": chunk["page_ref"] or ""},
        "embedding": {"B": _floats_to_bytes(embedding)},
        "created_at": {"S": datetime.datetime.utcnow().isoformat() + "Z"},
    }


def upload_pdf_to_s3(pdf_path: str, bucket: str, region: str) -> str:
    """Upload PDF to S3 and return s3:// URI."""
    s3 = boto3.client("s3", region_name=region)
    key = f"pdfs/{Path(pdf_path).name}"
    s3.upload_file(pdf_path, bucket, key)
    uri = f"s3://{bucket}/{key}"
    print(f"  Uploaded: {uri}")
    return uri


def ingest_pdf(pdf_path: str, table: str, bucket: str, region: str) -> int:
    """
    Full ingest pipeline for one PDF:
      1. Upload to S3
      2. Extract chunks
      3. Generate embeddings
      4. Write to DynamoDB

    Returns number of chunks written.
    """
    dynamo = boto3.client("dynamodb", region_name=region)
    upload_pdf_to_s3(pdf_path, bucket, region)
    chunks = extract_chunks_from_pdf(pdf_path)
    print(f"  Extracted {len(chunks)} chunks from {Path(pdf_path).name}")
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk["text"])
        item = build_dynamo_item(chunk, embedding)
        dynamo.put_item(TableName=table, Item=item)
        if (i + 1) % 10 == 0:
            print(f"    Written {i + 1}/{len(chunks)} chunks...")
    print(f"  Done: {len(chunks)} chunks written to {table}")
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs to DynamoDB + S3")
    parser.add_argument("--pdf-dir", default="data/pdfs", help="Directory containing PDFs")
    parser.add_argument("--table", default="voicebot_faqs", help="DynamoDB table name")
    parser.add_argument("--bucket", default="voicebot-mvp-docs", help="S3 bucket name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        return

    print(f"Found {len(pdfs)} PDFs to ingest:")
    total_chunks = 0
    for pdf in pdfs:
        print(f"\nIngesting: {pdf.name}")
        total_chunks += ingest_pdf(str(pdf), args.table, args.bucket, args.region)

    print(f"\nIngestion complete: {total_chunks} total chunks across {len(pdfs)} PDFs")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

```bash
pytest tests/knowledge/test_ingest_pipeline.py -v
```
Expected: `PASSED` (2 tests — unit tests use mocks, no real AWS)

**Step 5: Commit**

```bash
git add knowledge/pipeline/run_ingest.py tests/knowledge/test_ingest_pipeline.py
git commit -m "feat(01-06): add run_ingest.py — PDF to S3+DynamoDB with 384-dim embeddings"
```

---

## Task 2: Create S3 Bucket + DynamoDB Table (if not exists)

**Files:**
- Create: `infra/scripts/setup_aws_tables.py`

**Step 1: Write failing test**

```python
# tests/knowledge/test_ingest_pipeline.py — add:
from knowledge.pipeline.run_ingest import _floats_to_bytes
import struct

def test_floats_to_bytes_roundtrip():
    original = [0.5, -0.3, 1.0] + [0.0] * 381
    packed = _floats_to_bytes(original)
    unpacked = list(struct.unpack(f"<{len(original)}f", packed))
    assert abs(unpacked[0] - 0.5) < 1e-5
    assert abs(unpacked[1] - -0.3) < 1e-5
```

**Step 2: Run to verify it passes immediately (implementation already done)**

```bash
pytest tests/knowledge/test_ingest_pipeline.py -v
```
Expected: 3 tests `PASSED`

**Step 3: Create setup script `infra/scripts/setup_aws_tables.py`**

```python
"""
infra/scripts/setup_aws_tables.py
Creates DynamoDB tables + S3 bucket required for Phase 01.
Run once before ingesting PDFs.

Usage: python infra/scripts/setup_aws_tables.py --region ap-south-1
"""
import argparse
import boto3
from botocore.exceptions import ClientError


def create_faqs_table(dynamo, table_name: str):
    try:
        dynamo.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "chunk_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "chunk_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created DynamoDB table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table already exists: {table_name}")
        else:
            raise


def create_sessions_table(dynamo, table_name: str):
    try:
        dynamo.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "turn_number", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "turn_number", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created DynamoDB table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table already exists: {table_name}")
        else:
            raise


def create_s3_bucket(s3, bucket_name: str, region: str):
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"Created S3 bucket: {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"S3 bucket already exists: {bucket_name}")
        else:
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--bucket", default="voicebot-mvp-docs")
    args = parser.parse_args()

    dynamo = boto3.client("dynamodb", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)

    create_faqs_table(dynamo, "voicebot_faqs")
    create_sessions_table(dynamo, "voicebot_sessions")
    create_s3_bucket(s3, args.bucket, args.region)
    print("\nSetup complete. Run ingestion next:")
    print(f"  python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/")


if __name__ == "__main__":
    main()
```

**Step 4: Commit**

```bash
git add infra/scripts/setup_aws_tables.py
git commit -m "feat(01-06): add setup_aws_tables.py — create DynamoDB tables + S3 bucket"
```

---

## Task 3: Create 50-Turn WebSocket Test Script

**Files:**
- Create: `tests/e2e/run_50_turns.py`
- Create: `tests/e2e/sample_questions.json`

**Step 1: Create sample questions file**

```json
[
  "How do I apply for a building permit?",
  "What are the property tax payment deadlines?",
  "How do I register to vote in Jackson County?",
  "Where can I pay my water bill?",
  "What documents do I need for a zoning variance?",
  "How do I report a pothole on a county road?",
  "What are the recycling pickup days?",
  "How do I get a copy of my birth certificate?",
  "What is the process for a business license?",
  "How do I appeal my property assessment?",
  "Where is the nearest county health clinic?",
  "How do I apply for food assistance (SNAP)?",
  "What are the county court hours?",
  "How do I contest a traffic citation?",
  "Where do I renew my vehicle registration?",
  "What are the park and recreation programs?",
  "How do I report a stray animal?",
  "What permits do I need to add a fence?",
  "How do I find my polling location?",
  "What are the senior services available?",
  "How do I pay county court fees online?",
  "What is the deadline for homestead exemption?",
  "How do I get a septic permit?",
  "Where do I apply for emergency rental assistance?",
  "What are the hours for the county clerk office?",
  "How do I report code violations?",
  "What is the process for a name change?",
  "How do I get my criminal background check?",
  "What are the requirements for a vendor permit?",
  "How do I dispute my utility bill?",
  "Where can I find county budget documents?",
  "How do I apply for a job with the county?",
  "What are the flood zone regulations?",
  "How do I get a marriage license?",
  "What assistance is available after a disaster?",
  "How do I contact animal control?",
  "What are the county holiday schedules?",
  "How do I get a copy of a court record?",
  "What is the process for a land survey?",
  "How do I appeal a zoning decision?",
  "Where do I report elder abuse?",
  "What is the county tax rate?",
  "How do I get a library card?",
  "What are the requirements for a food truck permit?",
  "How do I schedule a county inspector?",
  "What mental health services does the county offer?",
  "How do I apply for disability accommodations?",
  "What are the noise ordinance rules?",
  "How do I find unclaimed property in the county?",
  "What are the regulations for short-term rentals?"
]
```

**Step 2: Create `tests/e2e/run_50_turns.py`**

```python
"""
tests/e2e/run_50_turns.py
Run 50 test voice turns against the ECS WebSocket endpoint and record results.

Usage:
  python tests/e2e/run_50_turns.py --host 65.0.116.5 --port 8000 --turns 50 --output results.json

Prerequisites:
  pip install websockets
"""
from __future__ import annotations
import argparse
import asyncio
import json
import time
import datetime
from pathlib import Path


async def run_turn(ws_url: str, question: str, token: str = "test-token") -> dict:
    """Send one text turn and measure latency. Returns result dict."""
    try:
        import websockets
    except ImportError:
        raise ImportError("pip install websockets")

    start = time.perf_counter()
    try:
        async with websockets.connect(
            f"{ws_url}?token={token}",
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            # Wait for ack
            ack = await asyncio.wait_for(ws.recv(), timeout=10)
            # Send question
            await ws.send(json.dumps({"type": "text", "text": question}))
            # Get response
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response = json.loads(raw)
            return {
                "question": question,
                "answer": response.get("text", ""),
                "latency_ms": round(elapsed_ms, 1),
                "slo_met": elapsed_ms < 1500,
                "status": "ok",
                "error": None,
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "question": question,
            "answer": None,
            "latency_ms": round(elapsed_ms, 1),
            "slo_met": False,
            "status": "error",
            "error": str(e),
        }


async def run_test(host: str, port: int, turns: int, output: str):
    questions_path = Path(__file__).parent / "sample_questions.json"
    with open(questions_path) as f:
        all_questions = json.load(f)

    questions = (all_questions * ((turns // len(all_questions)) + 1))[:turns]
    ws_url = f"ws://{host}:{port}/ws"

    print(f"Running {turns} turns against {ws_url}")
    print(f"Started: {datetime.datetime.now().isoformat()}\n")

    results = []
    for i, q in enumerate(questions, 1):
        result = await run_turn(ws_url, q)
        results.append(result)
        status = "OK" if result["status"] == "ok" else "ERROR"
        slo = "SLO" if result["slo_met"] else "SLOW"
        print(f"  [{i:02d}/{turns}] {status} {slo} {result['latency_ms']:.0f}ms — {q[:60]}")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "ok")
    slo_count = sum(1 for r in results if r["slo_met"])
    latencies = [r["latency_ms"] for r in results if r["status"] == "ok"]
    latencies.sort()

    def pct(lst, p):
        if not lst:
            return None
        idx = int(len(lst) * p / 100)
        return lst[min(idx, len(lst) - 1)]

    summary = {
        "total_turns": turns,
        "success_count": ok_count,
        "error_count": turns - ok_count,
        "slo_met_count": slo_count,
        "slo_met_pct": round(slo_count / turns * 100, 1),
        "latency_p50_ms": pct(latencies, 50),
        "latency_p95_ms": pct(latencies, 95),
        "latency_p99_ms": pct(latencies, 99),
        "estimated_cost_usd": round(ok_count * 0.016, 4),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    output_data = {"summary": summary, "turns": results}
    with open(output, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS: {ok_count}/{turns} success | SLO: {summary['slo_met_pct']}%")
    print(f"Latency — p50: {summary['latency_p50_ms']}ms | p95: {summary['latency_p95_ms']}ms")
    print(f"Est. cost: ${summary['estimated_cost_usd']:.4f} ({ok_count} turns × $0.016)")
    print(f"Results saved: {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="65.0.116.5")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--turns", type=int, default=50)
    parser.add_argument("--output", default="results.json")
    args = parser.parse_args()
    asyncio.run(run_test(args.host, args.port, args.turns, args.output))


if __name__ == "__main__":
    main()
```

**Step 3: Run a quick sanity check (no real AWS needed)**

```bash
# Verify the script is importable
python -c "import tests.e2e.run_50_turns; print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add tests/e2e/run_50_turns.py tests/e2e/sample_questions.json
git commit -m "feat(01-06): add run_50_turns.py — WebSocket test script with latency + cost tracking"
```

---

## Task 4: Create AWS CLI Testing Guide

**Files:**
- Create: `docs/AWS-CLI-TESTING-GUIDE.md`

**Step 1: Create the guide**

```bash
# No test needed — this is documentation. Write it directly.
```

Create `docs/AWS-CLI-TESTING-GUIDE.md`:

```markdown
# AWS CLI Testing Guide — Phase 01

**Region:** ap-south-1 (Mumbai)
**Cluster:** voice-bot-mvp-cluster
**API:** http://65.0.116.5:8000

---

## Prerequisites

```bash
# Verify AWS CLI is configured
aws sts get-caller-identity
# Expected: {"Account": "148952810686", "Arn": "arn:aws:iam::..."}
```

---

## Step 1: Setup AWS Tables + Bucket

```bash
python infra/scripts/setup_aws_tables.py --region ap-south-1
```

---

## Step 2: Place PDFs in data/pdfs/

```bash
mkdir -p data/pdfs
# Copy your 5 PDFs here
ls data/pdfs/
```

---

## Step 3: Ingest PDFs (S3 + DynamoDB + Embeddings)

```bash
# ~5-10 minutes per PDF depending on size
python -m knowledge.pipeline.run_ingest \
  --pdf-dir data/pdfs/ \
  --table voicebot_faqs \
  --bucket voicebot-mvp-docs \
  --region ap-south-1
```

---

## Step 4: Verify Ingest via AWS CLI

```bash
# Count chunks in DynamoDB
aws dynamodb scan \
  --table-name voicebot_faqs \
  --select COUNT \
  --region ap-south-1

# View one chunk (verify text + embedding)
aws dynamodb scan \
  --table-name voicebot_faqs \
  --limit 1 \
  --projection-expression "chunk_id, source_doc, department, created_at" \
  --region ap-south-1

# Verify PDFs in S3
aws s3 ls s3://voicebot-mvp-docs/pdfs/ --region ap-south-1
```

---

## Step 5: Check ECS Task is Running

```bash
# List running tasks
aws ecs list-tasks \
  --cluster voice-bot-mvp-cluster \
  --region ap-south-1

# Get task details (CPU/Memory usage)
TASK_ARN=$(aws ecs list-tasks \
  --cluster voice-bot-mvp-cluster \
  --query 'taskArns[0]' \
  --output text \
  --region ap-south-1)

aws ecs describe-tasks \
  --cluster voice-bot-mvp-cluster \
  --tasks $TASK_ARN \
  --query 'tasks[0].{Status:lastStatus,CPU:cpu,Memory:memory,CreatedAt:createdAt}' \
  --region ap-south-1

# Test API health
curl http://65.0.116.5:8000/health
```

---

## Step 6: Run 50-Turn Test

```bash
pip install websockets  # if not installed

python tests/e2e/run_50_turns.py \
  --host 65.0.116.5 \
  --port 8000 \
  --turns 50 \
  --output results.json

# View summary
python -c "
import json
with open('results.json') as f:
    d = json.load(f)
s = d['summary']
print(f'Success: {s[\"success_count\"]}/{s[\"total_turns\"]}')
print(f'SLO met: {s[\"slo_met_pct\"]}%')
print(f'p50: {s[\"latency_p50_ms\"]}ms | p95: {s[\"latency_p95_ms\"]}ms')
print(f'Est. cost: \${s[\"estimated_cost_usd\"]}')
"
```

---

## Step 7: Check CloudWatch Metrics

```bash
# Turn latency average (last hour)
aws cloudwatch get-metric-statistics \
  --namespace voicebot/latency \
  --metric-name TotalTurnLatency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average SampleCount \
  --region ap-south-1

# Cache hits vs misses
aws cloudwatch get-metric-statistics \
  --namespace voicebot/rag \
  --metric-name CacheHits \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum \
  --region ap-south-1
```

---

## Step 8: Check AWS Cost

```bash
# Monthly spend to date (Cost Explorer — always us-east-1)
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --region us-east-1

# ECS-specific cost (last 7 days)
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter '{"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Elastic Container Service"]}}' \
  --region us-east-1
```

---

## Expected Cost for 50-Turn Test

| Service | Amount |
|---------|--------|
| Amazon Bedrock (Claude) | ~$0.68 |
| ECS Fargate (existing task) | ~$0.04/hr (always running) |
| DynamoDB | $0 (free tier) |
| S3 | $0 (free tier) |
| **Total for test** | **~$0.72** |

---

## Troubleshooting

**"WebSocket connection refused"**
```bash
curl http://65.0.116.5:8000/health  # verify task is up
aws ecs list-tasks --cluster voice-bot-mvp-cluster --region ap-south-1
```

**"DynamoDB table not found"**
```bash
python infra/scripts/setup_aws_tables.py --region ap-south-1
```

**"No module named sentence_transformers"**
```bash
pip install sentence-transformers pdfplumber boto3 websockets
```
```

**Step 2: Commit**

```bash
git add docs/AWS-CLI-TESTING-GUIDE.md
git commit -m "docs(01-06): add AWS CLI testing guide — ingest → 50-turn test → cost check"
```

---

## Task 5: Update Phase Plan Files

**Files:**
- Update: `.planning/phases/01-runnable-mvp-web-voice/01-05-PLAN.md`
- Create: `.planning/phases/01-runnable-mvp-web-voice/01-06-PLAN.md`

**Step 1: No test needed — plan file update**

Update `01-05-PLAN.md` header to reflect real AWS:

```yaml
---
phase: 01
plan: 05
title: Local Observability Dashboard (Real AWS Data)
objective: Build a local web dashboard at /dashboard that displays real-time data from DynamoDB, CloudWatch, and Redis. Supports USE_AWS_MOCKS=true for offline dev and USE_AWS_MOCKS=false for production data.
autonomous: true
gap_closure: false
depends_on: [01-01, 01-02, 01-03, 01-04]
---
```

**Step 2: Create 01-06-PLAN.md**

```yaml
---
phase: 01
plan: 06
title: AWS CLI Testing Workflow (50-Turn Validation)
objective: Provide a complete end-to-end testing workflow — ingest 5 PDFs to S3+DynamoDB, run 50 voice turns via ECS API, verify via AWS CLI, document per-turn cost.
autonomous: false
gap_closure: false
depends_on: [01-01, 01-02, 01-03, 01-04, 01-05]
---
```

**Step 3: Commit**

```bash
git add .planning/phases/01-runnable-mvp-web-voice/
git commit -m "plan(01-06): add AWS CLI testing workflow plan + update 01-05 header"
```

---

## Full Workflow (Copy-Paste Order)

Once all code is implemented, run in this order:

```bash
# 1. Setup tables + bucket
python infra/scripts/setup_aws_tables.py --region ap-south-1

# 2. Place PDFs, then ingest
python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/ --region ap-south-1

# 3. Verify data
aws dynamodb scan --table-name voicebot_faqs --select COUNT --region ap-south-1
aws s3 ls s3://voicebot-mvp-docs/pdfs/ --region ap-south-1

# 4. Check ECS API
curl http://65.0.116.5:8000/health

# 5. Run 50-turn test
python tests/e2e/run_50_turns.py --turns 50 --output results.json

# 6. Check cost
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY --metrics BlendedCost --region us-east-1
```

---

## Success Criteria

- [ ] `python infra/scripts/setup_aws_tables.py` creates tables without error
- [ ] `python -m knowledge.pipeline.run_ingest` ingests 5 PDFs — chunks in DynamoDB with embeddings
- [ ] `aws dynamodb scan --table-name voicebot_faqs --select COUNT` returns > 0
- [ ] `aws s3 ls s3://voicebot-mvp-docs/pdfs/` shows 5 PDFs
- [ ] `curl http://65.0.116.5:8000/health` returns `{"status": "ok"}`
- [ ] `run_50_turns.py` completes 50/50 turns, 0 errors
- [ ] SLO met ≥ 80% of turns (latency < 1500ms)
- [ ] Estimated cost ≤ $0.80 for 50 turns
- [ ] AWS CLI cost report confirms spend within budget
