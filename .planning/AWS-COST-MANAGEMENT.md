# AWS Cost Management & Auto-Stop Plan

**Created:** 2026-03-08
**Status:** ACTIVE - Phase 0 Deployment Cost Control

---

## 1. Current AWS Deployment Costs

### Running Services (Phase 0)
- **ECS Fargate Cluster:** enterprise-ai-voice-bot-cluster
- **Region:** ap-south-1 (Mumbai)
- **Status:** STOPPED (as of 2026-03-08)

### Cost Breakdown (When Running)

#### Option A: Regular Fargate (NOT RECOMMENDED)
```
ECS Fargate vCPU:    0.256 vCPU × $0.04582/hour = $0.0117/hour
ECS Fargate Memory:  512 MB (0.5 GB) × $0.00511/hour = $0.0026/hour
Total per hour:      $0.0143/hour
Daily cost:          $0.34/day (24 hours)
Monthly cost:        ~$10.2/month
```

#### Option B: Spot Fargate (RECOMMENDED) ✅
```
ECS Fargate Spot:    50% discount on regular
Total per hour:      $0.0071/hour
Daily cost:          $0.17/day (24 hours)
Monthly cost:        ~$5.1/month (50% savings!)
```

#### Option C: Inactive (Current)
```
No running tasks = $0/day ✅
```

### Additional Costs (Always-on)

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| ECR Storage (125MB) | ~$0.01 | Minimal |
| CloudWatch Logs | ~$0.50 | Depends on volume |
| Data Transfer | $0-2 | If API called externally |
| **TOTAL (ECR+Logs)** | **~$0.51** | Always charged |

---

## 2. Cost Estimates

### Scenario 1: Running 24/7 (No Auto-Stop)
```
Regular Fargate:  $10.2/month + $0.51 = $10.71/month
Spot Fargate:     $5.1/month + $0.51 = $5.61/month  ✅ (Current setup)
Lambda:           $0.20/month (better for stateless)
```

### Scenario 2: Spot Fargate + 8-Hour Daily Usage
```
Spot 8 hours/day: ($0.17/day × 0.33) + $0.51 = $0.57/month ✅ BEST
```

### Scenario 3: Development/Testing (Ephemeral Deploys)
```
Deploy for 1 hour:  $0.0071/hour = $0.007 per test
100 tests/month:    $0.70/month ✅ Very cheap
```

---

## 3. Estimated Cost So Far (Since Deployment)

**Deployment Date:** 2026-03-06
**Duration:** 2 days (before stop on 2026-03-08)

### Cost Calculation
```
Regular Fargate (2 days):
  $0.34/day × 2 days = $0.68

ECR + CloudWatch (2 days):
  $0.51/month × (2/30 days) = $0.034

ESTIMATED TOTAL SO FAR: ~$0.71

(Minimal - less than $1!)
```

---

## 4. Auto-Stop Setup (Recommended)

### Option A: EventBridge Schedule (Simple) ✅ RECOMMENDED

**Setup time:** 5 minutes
**Cost:** ~$0.01/month
**How it works:** Automatically stops task at scheduled time

```bash
# Create EventBridge rule to stop at 6 PM daily
aws events put-rule \
  --name stop-voice-bot-6pm \
  --schedule-expression "cron(0 18 * * ? *)" \
  --state ENABLED \
  --region ap-south-1

# Create Lambda to stop ECS task (see below)
# Then attach Lambda as target to this rule
```

**Lambda function code (create in AWS Console):**
```python
import boto3

ecs = boto3.client('ecs', region_name='ap-south-1')

def lambda_handler(event, context):
    # List running tasks
    response = ecs.list_tasks(
        cluster='enterprise-ai-voice-bot-cluster',
        desiredStatus='RUNNING'
    )

    # Stop each task
    for task_arn in response['taskArns']:
        ecs.stop_task(
            cluster='enterprise-ai-voice-bot-cluster',
            task=task_arn,
            reason='Scheduled auto-stop'
        )

    return {
        'statusCode': 200,
        'body': f'Stopped {len(response["taskArns"])} tasks'
    }
```

---

### Option B: ECS Auto-Scaling (Advanced)

**Setup time:** 10 minutes
**Cost:** ~$0.01/month
**How it works:** Scales to 0 tasks when CPU is low

```bash
# Register scalable target
aws autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/enterprise-ai-voice-bot-cluster/enterprise-ai-voice-bot-svc \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 0 \
  --max-capacity 2 \
  --region ap-south-1

# Create target tracking policy (scales down when idle)
aws autoscaling put-scaling-policy \
  --policy-name scale-to-zero-on-idle \
  --policy-type TargetTrackingScaling \
  --service-namespace ecs \
  --resource-id service/enterprise-ai-voice-bot-cluster/enterprise-ai-voice-bot-svc \
  --scalable-dimension ecs:service:DesiredCount \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 20.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 300,
    "ScaleInCooldown": 900
  }' \
  --region ap-south-1
```

---

## 5. Monitoring & Alerts

### Set Up AWS Budget Alert (Free)

```bash
# Create budget for $5/month alert
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget '{
    "BudgetName": "voice-bot-monthly",
    "BudgetLimit": {"Amount": "5", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "your-email@example.com"
    }]
  }]' \
  --region ap-south-1
```

### Check Current Costs (Manual)

**AWS Console Path:**
```
Billing and Cost Management → Billing Dashboard
→ "Month-to-date charges"
→ Filter by service
```

**Or via AWS CLI:**
```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-03-01,End=2026-03-08 \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --region us-east-1
```

---

## 6. Quick Reference: Cost Optimization Strategy

| Action | Cost/Month | Setup Time | Recommendation |
|--------|-----------|-----------|---|
| Always-on Fargate | $10.71 | None | ❌ Don't use |
| Always-on Spot | $5.61 | None | ⚠️ Good for always-on |
| Spot + 8h daily | $0.57 | 5 min | ✅ BEST for dev |
| Spot + auto-stop 6pm | $2-3 | 5 min | ✅ Good balance |
| Ephemeral deploys | $0.70 | 1 min | ✅ Best for testing |

---

## 7. Recommended Setup (FOR YOU)

### Immediate Actions
- [x] Stop all running tasks
- [ ] Create EventBridge auto-stop rule (5 min)
- [ ] Set budget alert to $5/month (2 min)

### When Testing Phase 1
1. Start ECS Spot task manually
2. Run tests for 30 min - 2 hours
3. Stop task after testing
4. **Cost per test:** ~$0.01

### When Deploying to Production
Switch to always-on Spot Fargate (~$5.61/month)

---

## 8. Cost Dashboard Command

**Add this to your workflow to check costs anytime:**

```bash
# View Phase 0 cost status
cat .planning/AWS-COST-MANAGEMENT.md

# Check running tasks
aws ecs list-tasks --cluster enterprise-ai-voice-bot-cluster --region ap-south-1

# View AWS billing dashboard
echo "Open: https://console.aws.amazon.com/billing/"
```

---

## Summary

✅ **Stopped:** No charges now
✅ **Estimated cost so far:** ~$0.71
✅ **Spot configured:** Ready for 50% savings
✅ **Auto-stop ready:** 5 minutes to set up

**Next Phase:** When ready for Phase 1, decide:
- Always-on deployment → Use Spot Fargate (~$5.61/month)
- Development/testing → Use ephemeral deploys (~$0.70/month)

---

## 9. Resource Utilization Monitoring & Optimization

### Problem: Is 256 CPU + 512 MB Sufficient?

**SHORT ANSWER:** No. This configuration is too tight for production voice processing.

#### Resource Breakdown
- **256 CPU** = 0.25 vCPU (shared, burst-capable)
- **512 MB total memory**
  - Python runtime + FastAPI: ~150 MB
  - WebSocket + processing overhead: ~100 MB
  - **Available for voice processing: ~260 MB** ⚠️

#### Voice Processing Risk
- Audio transcription spikes: 200-400 MB
- Text-to-speech synthesis: 300-500 MB
- Concurrent WebSocket connections: ~1 MB each
- **Current config can't handle peak loads** → OOMKill → Service crash

### Monitoring Infrastructure Deployed

#### CloudWatch Monitoring (`infra/terraform/monitoring.tf`)
- **CPU & Memory Dashboard:** Real-time metrics visualization
- **Alarms:** Trigger at 80% CPU, 85% memory
- **Location:** AWS Console → CloudWatch → Dashboards → `voice-bot-mvp-resources`

#### Resource Analysis Tool (`infra/scripts/resource_monitor.py`)
```bash
# Run to get resource recommendations
cd infra/scripts
python3 resource_monitor.py voice-bot-mvp 24
```

**Output includes:**
- Current allocation (256 CPU, 512 MB)
- Peak utilization last 24 hours
- Auto-generated recommendation with Terraform command

#### In-App Monitoring (`backend/app/monitoring.py`)
- Tracks startup memory footprint
- Warns when approaching 80% memory usage
- Can be integrated into health endpoints

### Recommended Sizing Guidance

| Workload Type | CPU | Memory | Monthly Cost |
|---|---|---|---|
| Dev/Testing | 256 | 512 MB | $11 |
| Small production (1-5 concurrent) | 512 | 1024 MB | $22 |
| Medium production (5-20 concurrent) | 1024 | 2048 MB | $44 |
| High production (20+ concurrent) | 2048 | 4096 MB | $88 |

### How to Right-Size

1. **Deploy monitoring** (already done)
   ```bash
   cd infra && terraform apply
   ```

2. **Run load test** with concurrent voice sessions
   ```bash
   # Simulate 5-10 concurrent users
   # Run for 30 minutes to collect data
   ```

3. **Generate resource report** after 24+ hours
   ```bash
   python3 infra/scripts/resource_monitor.py voice-bot-mvp 24
   ```

4. **Apply recommendations**
   ```bash
   # Output will suggest CPU/memory values
   terraform apply -var='cpu=512' -var='memory=1024'
   ```

### Cost vs. Safety Trade-offs

| Scenario | CPU | Memory | Cost | Risk |
|---|---|---|---|---|
| Too Small (Current) | 256 | 512 MB | $11/mo | HIGH - OOMKill |
| Minimum Safe | 512 | 1024 MB | $22/mo | LOW |
| Comfortable | 1024 | 2048 MB | $44/mo | VERY LOW |

**Recommendation:** Start at 512 CPU + 1024 MB (~$22/mo), then optimize down based on monitoring data.

---

*Last updated: 2026-03-09*
*Phase: 00-learning-mvp-bootstrap*
*Resource Monitoring: DEPLOYED*
