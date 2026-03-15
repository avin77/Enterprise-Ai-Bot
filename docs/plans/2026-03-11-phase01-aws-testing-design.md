# Phase 01: Real AWS Testing + Dashboard Update Design

**Date:** 2026-03-11
**Scope:** Phase 01 plans 01-05 (update) + 01-06 (new)
**Author:** Brainstorming session — approved by user

---

## Context

Phase 01 has 4 completed plans (01-01 through 01-04). This document covers:
- **01-05 update:** Local observability dashboard connects to real DynamoDB (not mock)
- **01-06 new:** AWS CLI testing workflow — PDF ingest, embeddings, 50-turn API test, cost tracking

---

## AWS Setup

### User's Account
- **Account:** 148952810686
- **Region:** ap-south-1 (Mumbai)
- **Credit:** $200 AWS credit (free tier + credits)
- **Test volume:** 50 voice turns, 5 PDFs, 1 concurrent user

### Free Tier Coverage (always-free)
| Service | Free Tier | 50-turn test usage | Cost |
|---------|-----------|-------------------|------|
| DynamoDB | 25 RCU/WCU + 25 GB/month | ~400 ops, ~1 MB | $0 |
| S3 | 5 GB + 20k GETs + 2k PUTs | 5 PDFs (~100 KB) + 100 ops | $0 |
| CloudWatch Logs | 5 GB/month | ~50 KB | $0 |

### Pay-Per-Use (no free tier)
| Service | Rate | 50-turn test | Cost |
|---------|------|-------------|------|
| Bedrock (Claude Sonnet) | $3.00/$15.00 per 1M tokens in/out | 100k in + 25k out tokens | ~$0.68 |
| ECS Fargate | ~$0.04/vCPU-hr + ~$0.004/GB-hr | 1 task running (existing) | ~$0.04/hr (already running) |
| **Total for 50 test turns** | — | — | **~$0.72** |

### Per-Turn Cost Breakdown
| Component | Cost |
|-----------|------|
| Bedrock (2k input + 500 output tokens) | $0.0134 |
| DynamoDB (1 write + 5 reads) | <$0.0001 |
| ECS compute (amortized) | $0.0024 |
| S3 (1 GET for PDF chunk) | <$0.0001 |
| **Total per turn** | **~$0.016** |

---

## Architecture (Single Setup)

```
Your AWS Account (ap-south-1)
├── ECS Fargate Task (existing, voice-bot-mvp-cluster)
│   ├── FastAPI :8000 — Orchestrator + WebSocket + /api/* endpoints
│   ├── Embedding service (all-MiniLM-L6-v2, in-memory)
│   ├── BM25 reranker (rank_bm25, in-memory)
│   └── Redis sidecar (in-task)
├── DynamoDB Tables
│   ├── voicebot_faqs — 5 PDFs chunked, with 384-dim embeddings
│   ├── voicebot_sessions — 50 test turns, session tracking
│   └── voicebot_metrics — cost/latency per turn
├── S3 Bucket
│   └── 5 test PDFs (raw source documents)
├── CloudWatch
│   └── Logs + custom metrics (cost, latency, cache hits)
└── Bedrock
    └── Claude Sonnet 4.6 (ap-south-1)
```

---

## Plan 01-05 Update: Dashboard Connects to Real AWS

**Change from current plan:** Instead of in-memory mock data, dashboard polls:
- Real DynamoDB `voicebot_faqs` for knowledge base stats
- Real DynamoDB `voicebot_sessions` for conversation tracking
- Real CloudWatch metrics for latency + cost per turn
- Real Redis stats (hit/miss ratio)

**No code path changes** — only configuration changes:
- `DYNAMODB_MOCK=false` env var switches from mock to real DynamoDB
- Dashboard endpoints proxy to real DynamoDB via boto3

---

## Plan 01-06 New: AWS CLI Testing Workflow

### Task 1: PDF Ingest to S3 + DynamoDB with Embeddings

**Process:**
1. User places 5 PDFs in `data/pdfs/` folder
2. Run `python knowledge/pipeline/ingest.py` locally
3. Pipeline does:
   - Extract text from PDF (PyPDF2)
   - Chunk text (500 tokens, 50 overlap)
   - Generate 384-dim embeddings (all-MiniLM-L6-v2)
   - Upload PDF to S3 (`s3://voicebot-mvp-docs/pdfs/`)
   - Write chunks + embeddings to DynamoDB (`voicebot_faqs`)

**Verify via AWS CLI:**
```bash
# Check S3 PDFs uploaded
aws s3 ls s3://voicebot-mvp-docs/pdfs/ --region ap-south-1

# Check DynamoDB FAQ chunks
aws dynamodb scan --table-name voicebot_faqs \
  --select COUNT --region ap-south-1

# View a single chunk (verify embedding exists)
aws dynamodb scan --table-name voicebot_faqs \
  --limit 1 --region ap-south-1
```

### Task 2: Run 50 Test Voice Turns via API

**API endpoint:** `http://65.0.116.5:8000/voice` (WebSocket)
**Test script:** `tests/e2e/run_50_turns.py`

```bash
# Test the REST health endpoint first
curl http://65.0.116.5:8000/health

# Run 50 test turns with sample questions
python tests/e2e/run_50_turns.py --turns 50 --output results.json
```

### Task 3: Check AWS Metrics + Cost via CLI

```bash
# ECS task status
aws ecs describe-tasks \
  --cluster voice-bot-mvp-cluster \
  --tasks $(aws ecs list-tasks --cluster voice-bot-mvp-cluster \
    --query 'taskArns[0]' --output text) \
  --region ap-south-1

# CloudWatch: avg latency last hour
aws cloudwatch get-metric-statistics \
  --namespace voicebot/latency \
  --metric-name TotalTurnLatency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 --statistics Average \
  --region ap-south-1

# Cost Explorer: today's spend
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --region us-east-1
```

### Task 4: Verify DynamoDB Sessions + Cost per Turn

```bash
# List all test sessions
aws dynamodb scan --table-name voicebot_sessions \
  --region ap-south-1

# Check metrics table (cost + latency logged per turn)
aws dynamodb scan --table-name voicebot_metrics \
  --region ap-south-1
```

---

## Success Criteria

### 01-05 Dashboard
- [ ] Dashboard shows real DynamoDB FAQ count (not mock "12 FAQs")
- [ ] Dashboard shows real CloudWatch latency metrics
- [ ] Dashboard shows real session tracking (voicebot_sessions)
- [ ] Works with `DYNAMODB_MOCK=false` env var

### 01-06 AWS Testing Workflow
- [ ] 5 PDFs ingested to S3 and DynamoDB with embeddings
- [ ] 50 test turns complete via API (0 failures)
- [ ] AWS CLI commands verify: DynamoDB chunks, S3 PDFs, CloudWatch metrics
- [ ] Cost report shows per-turn cost ≤ $0.03 (alert threshold)
- [ ] Results JSON saved for baseline comparison

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `knowledge/pipeline/ingest.py` | Create/update | PDF → S3 + DynamoDB with embeddings |
| `tests/e2e/run_50_turns.py` | Create | 50-turn API test script |
| `docs/AWS-CLI-TESTING-GUIDE.md` | Create | Step-by-step AWS CLI testing guide |
| `backend/app/config.py` | Update | `DYNAMODB_MOCK` env var flag |
| `.planning/phases/01-runnable-mvp-web-voice/01-05-PLAN.md` | Update | Real DynamoDB instead of mock |
| `.planning/phases/01-runnable-mvp-web-voice/01-06-PLAN.md` | Create | AWS CLI testing workflow |
