# AWS CLI Testing Guide — Phase 01 End-to-End Workflow

**Audience:** Developer running Phase 01 validation for the first time.
**Region:** ap-south-1 (Mumbai) — all commands default to this unless noted.
**Goal:** Walk from zero to a verified 50-turn test with cost confirmation, top to bottom in one session.

---

## 1. Prerequisites — Verify AWS CLI is Configured

```bash
aws sts get-caller-identity
```

**Expected output:**

```json
{
    "UserId": "AIDA...",
    "Account": "148952810686",
    "Arn": "arn:aws:iam::148952810686:user/your-iam-user"
}
```

If you see `Unable to locate credentials`, run `aws configure` and provide your Access Key ID, Secret Access Key, and default region (`ap-south-1`).

**Also verify Python packages are installed:**

```bash
pip install boto3 pdfplumber sentence-transformers numpy websockets
```

---

## 2. Setup DynamoDB Tables and S3 Bucket

Run this once before ingesting any PDFs. The script is idempotent — safe to re-run if tables already exist.

```bash
python infra/scripts/setup_aws_tables.py --region ap-south-1
```

**Expected output:**

```
Setting up Phase 01 AWS resources...
  Created table: voicebot_faqs
  Created table: voicebot_sessions
  Created S3 bucket: voicebot-mvp-docs

Setup complete. Next step:
  python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/
```

If a table or bucket already exists, the script prints `already exists` and continues — this is not an error.

**Verify tables are active:**

```bash
aws dynamodb describe-table --table-name voicebot_faqs --region ap-south-1 \
  --query "Table.TableStatus"
```

Expected: `"ACTIVE"`

```bash
aws dynamodb describe-table --table-name voicebot_sessions --region ap-south-1 \
  --query "Table.TableStatus"
```

Expected: `"ACTIVE"`

---

## 3. Place PDFs in the Ingest Directory

```bash
mkdir -p data/pdfs
```

Copy your county/department PDFs into `data/pdfs/`. The ingest pipeline infers department from filename keywords:

| Keyword in filename | Inferred department |
|---------------------|---------------------|
| `permit`, `zoning`, `building` | planning |
| `tax`, `payment`, `budget` | finance |
| `election`, `voter` | elections |
| `road`, `traffic`, `pothole` | public-works |
| `recycl`, `waste`, `water`, `trash` | utilities |
| `park`, `recreation` | parks |
| `sheriff`, `police` | sheriff |
| `snap`, `food`, `senior` | human-services |
| *(anything else)* | general |

**Example:**

```bash
# Linux / macOS
cp ~/Downloads/county-permit-guide.pdf data/pdfs/
cp ~/Downloads/tax-payment-faq.pdf data/pdfs/

# Windows (PowerShell)
Copy-Item "$env:USERPROFILE\Downloads\county-permit-guide.pdf" data\pdfs\
```

Confirm files are in place:

```bash
ls -lh data/pdfs/
```

---

## 4. Ingest PDFs into DynamoDB and S3

```bash
python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/ --region ap-south-1
```

**Expected output (one line per PDF):**

```
Ingesting data/pdfs/county-permit-guide.pdf ...
  Extracted 12 chunks (dept: planning)
  Stored 12 chunks to DynamoDB voicebot_faqs
  Uploaded data/pdfs/county-permit-guide.pdf to s3://voicebot-mvp-docs/pdfs/county-permit-guide.pdf
Ingesting data/pdfs/tax-payment-faq.pdf ...
  Extracted 8 chunks (dept: finance)
  Stored 8 chunks to DynamoDB voicebot_faqs
  Uploaded data/pdfs/tax-payment-faq.pdf to s3://voicebot-mvp-docs/pdfs/tax-payment-faq.pdf

Ingest complete: 2 PDFs, 20 chunks total.
```

Each chunk is ~300 words with 40-word overlap. The pipeline also generates 384-dim embeddings (stored as DynamoDB Binary) for future Phase 4 hybrid search — this does not affect BM25 retrieval in Phase 1.

---

## 5. Verify DynamoDB Ingest

**Count all ingested chunks:**

```bash
aws dynamodb scan \
  --table-name voicebot_faqs \
  --select COUNT \
  --region ap-south-1
```

**Expected output:**

```json
{
    "Count": 20,
    "ScannedCount": 20,
    "ConsumedCapacity": null
}
```

**View one chunk to confirm structure:**

```bash
aws dynamodb scan \
  --table-name voicebot_faqs \
  --limit 1 \
  --region ap-south-1 \
  --query "Items[0].{chunk_id: chunk_id.S, department: department.S, source_doc: source_doc.S, text_preview: text.S}" \
  --output json
```

**Expected output:**

```json
{
    "chunk_id": "county-permit-guide.pdf:chunk:0",
    "department": "planning",
    "source_doc": "county-permit-guide.pdf",
    "text_preview": "Building permits are required for any construction..."
}
```

---

## 6. Verify S3 Upload

```bash
aws s3 ls s3://voicebot-mvp-docs/pdfs/ --region ap-south-1
```

**Expected output:**

```
2026-03-12 10:23:45     142830 county-permit-guide.pdf
2026-03-12 10:23:52      98412 tax-payment-faq.pdf
```

One line per PDF you ingested. If the listing is empty, re-run the ingest step — the S3 upload runs after DynamoDB storage.

---

## 7. Check ECS Task Health

**List running tasks in the cluster:**

```bash
aws ecs list-tasks \
  --cluster voice-bot-mvp-cluster \
  --desired-status RUNNING \
  --region ap-south-1
```

**Expected output:**

```json
{
    "taskArns": [
        "arn:aws:ecs:ap-south-1:148952810686:task/voice-bot-mvp-cluster/abc123def456"
    ]
}
```

If `taskArns` is empty, the service is not running. Check `aws ecs describe-services --cluster voice-bot-mvp-cluster --services voice-bot-mvp-svc --region ap-south-1`.

**Describe the task (CPU and memory):**

```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster voice-bot-mvp-cluster \
  --desired-status RUNNING \
  --region ap-south-1 \
  --query "taskArns[0]" \
  --output text)

aws ecs describe-tasks \
  --cluster voice-bot-mvp-cluster \
  --tasks "$TASK_ARN" \
  --region ap-south-1 \
  --query "tasks[0].{cpu: cpu, memory: memory, lastStatus: lastStatus, healthStatus: healthStatus}"
```

**Expected output:**

```json
{
    "cpu": "256",
    "memory": "512",
    "lastStatus": "RUNNING",
    "healthStatus": "HEALTHY"
}
```

**Test the HTTP health endpoint:**

```bash
curl http://65.0.116.5:8000/health
```

**Expected output:**

```json
{"status": "ok"}
```

---

## 8. Run 50-Turn End-to-End Test

```bash
python tests/e2e/run_50_turns.py --turns 50 --output results.json
```

**Expected console output (one line per turn):**

```
[Turn  1/50] query="How do I renew my building permit?" latency=1.23s sources=3
[Turn  2/50] query="What are property tax deadlines?" latency=0.98s sources=2
...
[Turn 50/50] query="Who manages road maintenance?" latency=1.07s sources=4

=== 50-Turn Test Summary ===
Total turns  : 50
Pass         : 48  (96.0%)
Fail         : 2   (4.0%)
Avg latency  : 1.12s
P95 latency  : 1.89s
Results saved: results.json
```

**View the summary from the JSON file:**

```bash
python -c "
import json, sys
data = json.load(open('results.json'))
summary = data.get('summary', data)
print(json.dumps(summary, indent=2))
"
```

**View failing turns only:**

```bash
python -c "
import json
data = json.load(open('results.json'))
fails = [t for t in data.get('turns', []) if not t.get('pass')]
for f in fails:
    print(f'Turn {f[\"turn\"]}: {f[\"query\"]}')
    print(f'  Error: {f.get(\"error\", \"no sources returned\")}')
"
```

---

## 9. Check CloudWatch Metrics — TotalTurnLatency

**Note on timestamps:** Cost Explorer always requires `--region us-east-1` (step 10). All other CloudWatch calls use `--region ap-south-1`.

**Linux — last 1 hour:**

```bash
START_TIME=$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
```

**macOS — last 1 hour:**

```bash
START_TIME=$(date -u -v-1H '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
```

**Fetch TotalTurnLatency statistics:**

```bash
aws cloudwatch get-metric-statistics \
  --namespace voicebot/latency \
  --metric-name TotalTurnLatency \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Average Minimum Maximum SampleCount \
  --unit Milliseconds \
  --region ap-south-1
```

**Expected output:**

```json
{
    "Datapoints": [
        {
            "Timestamp": "2026-03-12T10:00:00+00:00",
            "SampleCount": 50.0,
            "Average": 1123.4,
            "Minimum": 870.1,
            "Maximum": 1987.3,
            "Unit": "Milliseconds"
        }
    ],
    "Label": "TotalTurnLatency"
}
```

If `Datapoints` is empty, the 50-turn test either has not yet published metrics or the metric name does not match. Verify with:

```bash
aws cloudwatch list-metrics \
  --namespace voicebot/latency \
  --region ap-south-1
```

---

## 10. Check Cost — Monthly Total and ECS-Specific

**Note:** AWS Cost Explorer API always requires `--region us-east-1`, regardless of where your resources run.

**Linux — date helpers:**

```bash
MONTH_START=$(date -u -d "$(date +%Y-%m-01)" '+%Y-%m-%d')
TODAY=$(date -u '+%Y-%m-%d')
WEEK_AGO=$(date -u -d '7 days ago' '+%Y-%m-%d')
```

**macOS — date helpers:**

```bash
MONTH_START=$(date -u -v1d '+%Y-%m-%d')
TODAY=$(date -u '+%Y-%m-%d')
WEEK_AGO=$(date -u -v-7d '+%Y-%m-%d')
```

**Monthly total cost (current month):**

```bash
aws ce get-cost-and-usage \
  --time-period Start="$MONTH_START",End="$TODAY" \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --region us-east-1
```

**Expected output:**

```json
{
    "ResultsByTime": [
        {
            "TimePeriod": {"Start": "2026-03-01", "End": "2026-03-12"},
            "Total": {
                "BlendedCost": {"Amount": "0.72", "Unit": "USD"}
            }
        }
    ]
}
```

**ECS-specific cost — last 7 days:**

```bash
aws ce get-cost-and-usage \
  --time-period Start="$WEEK_AGO",End="$TODAY" \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter '{
    "Dimensions": {
      "Key": "SERVICE",
      "Values": ["Amazon Elastic Container Service"]
    }
  }' \
  --region us-east-1
```

**Expected output (one entry per day):**

```json
{
    "ResultsByTime": [
        {
            "TimePeriod": {"Start": "2026-03-05", "End": "2026-03-06"},
            "Total": {"BlendedCost": {"Amount": "0.0080", "Unit": "USD"}}
        },
        {
            "TimePeriod": {"Start": "2026-03-06", "End": "2026-03-07"},
            "Total": {"BlendedCost": {"Amount": "0.0080", "Unit": "USD"}}
        }
    ]
}
```

---

## 11. Expected Cost Table — 50-Turn Test Session

| Service | Usage | Estimated Cost |
|---------|-------|---------------|
| Amazon Bedrock (Haiku — Orchestrator/Supervisor) | ~50 turns × 500 input tokens + 100 output tokens | ~$0.04 |
| Amazon Bedrock (Sonnet — Response Agent) | ~50 turns × 800 input tokens + 300 output tokens | ~$0.64 |
| ECS Fargate (256 CPU / 512 MB) | ~1 hour session | ~$0.04 |
| DynamoDB (PAY_PER_REQUEST) | 50 reads + 50 writes (voicebot_faqs + voicebot_sessions) | $0.00 (free tier) |
| S3 (voicebot-mvp-docs) | < 100 MB stored, < 1000 GET requests | $0.00 (free tier) |
| CloudWatch (metrics + logs) | 4 custom metrics, standard logs | ~$0.00 |
| **Total (50 turns)** | | **~$0.72** |

**Per-turn cost breakdown:**

- Compute (ECS): ~$0.005/turn
- LLM (Bedrock): ~$0.010/turn
- **Total: ~$0.015/turn** (alert threshold: $0.03/turn)

These figures assume ap-south-1 Bedrock pricing. Actual cost varies with query length and retrieved context size.

---

## 12. Troubleshooting

### Issue 1: WebSocket Connection Refused

**Symptom:**

```
ConnectionRefusedError: [Errno 111] Connection refused
# or
websockets.exceptions.ConnectionClosedError: received 1006
```

**Diagnosis:**

```bash
# Check if ECS task is running
aws ecs list-tasks \
  --cluster voice-bot-mvp-cluster \
  --desired-status RUNNING \
  --region ap-south-1

# Check health endpoint
curl -v http://65.0.116.5:8000/health

# Check service events for recent failures
aws ecs describe-services \
  --cluster voice-bot-mvp-cluster \
  --services voice-bot-mvp-svc \
  --region ap-south-1 \
  --query "services[0].events[:5]"
```

**Fix:** If no tasks are running, force a new deployment:

```bash
aws ecs update-service \
  --cluster voice-bot-mvp-cluster \
  --service voice-bot-mvp-svc \
  --force-new-deployment \
  --region ap-south-1
```

Wait ~2 minutes, then re-check with `curl http://65.0.116.5:8000/health`.

---

### Issue 2: DynamoDB Table Not Found

**Symptom:**

```
botocore.errorfactory.ResourceNotFoundException:
  Requested resource not found: Table: voicebot_faqs not found
```

**Diagnosis:**

```bash
aws dynamodb list-tables --region ap-south-1
```

**Fix:** Re-run the setup script:

```bash
python infra/scripts/setup_aws_tables.py --region ap-south-1
```

If the table appears in `list-tables` but is still not found at runtime, confirm your boto3 client is using `region_name="ap-south-1"`. A client defaulting to `us-east-1` will not find tables created in Mumbai.

---

### Issue 3: Missing Python Packages

**Symptom:**

```
ImportError: No module named 'pdfplumber'
# or
ImportError: No module named 'sentence_transformers'
# or
ModuleNotFoundError: No module named 'websockets'
```

**Fix — install all required packages at once:**

```bash
pip install \
  boto3 \
  pdfplumber \
  sentence-transformers \
  numpy \
  websockets \
  pytest \
  pytest-asyncio
```

**Note:** `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~91 MB) on first use. This happens during ingest, not during query-time BM25 retrieval. Ensure you have network access and ~200 MB free disk space when running ingest for the first time.

**Verify the install:**

```bash
python -c "import boto3, pdfplumber, sentence_transformers, numpy, websockets; print('All packages OK')"
```
