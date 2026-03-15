# Senior PM Dashboard - Fully Automated Deployment

**Status:** ✅ READY - One Command Deployment
**Time Required:** 5 minutes (fully automated)
**Region:** ap-south-1 (Mumbai)

---

## What Gets Deployed

### ✅ CloudWatch Dashboard
- **Name:** `voice-bot-mvp-operations`
- **Widgets:** 14 (CPU, Memory, Cost, Tasks, Trends, Logs)
- **Update Frequency:** Real-time from ECS + every 15 min custom metrics
- **Accessible:** Via AWS Console or direct URL

### ✅ Lambda Function
- **Name:** `voice-bot-mvp-metrics-publisher`
- **Runtime:** Python 3.11
- **Function:** Collects ECS metrics & calculates costs
- **Triggered:** Every 15 minutes by EventBridge
- **No manual scheduling needed**

### ✅ EventBridge Trigger
- **Name:** `voice-bot-mvp-metrics-schedule`
- **Schedule:** Every 15 minutes (automatic)
- **Action:** Invokes Lambda function
- **No configuration needed**

### ✅ Custom Metrics Published
```
voicebot/operations/HourlyCost    → $0.01245
voicebot/operations/DailyCost     → $0.2988
voicebot/operations/MonthlyCost   → $8.96
voicebot/operations/IdleTasks     → 0 (count)
```

### ✅ IAM Roles & Policies
- Lambda execution role with ECS & CloudWatch permissions
- No secrets stored, uses AWS managed credentials
- All least-privilege permissions

---

## Deployment: One Command

```powershell
cd C:\Coding\Enterprise-AI-Voice-Bot
.\deploy-dashboard.ps1
```

**That's it!** Everything is deployed automatically.

---

## What Happens When You Run It

```
[CHECK] Verifying prerequisites (AWS CLI, Terraform, Credentials)
[INIT]  Initializing Terraform
[PLAN]  Creating deployment plan
[APPLY] Deploying infrastructure

[SUCCESS]
✓ CloudWatch Dashboard created
✓ Lambda function deployed
✓ EventBridge trigger configured
✓ All metrics connected
```

**Estimated time:** 2-3 minutes

---

## Post-Deployment: What You'll See

### 1. Dashboard Available Immediately
```
https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=voice-bot-mvp-operations
```

**Dashboard shows:**
- CPU: 0.55% (real-time)
- Memory: 11.5% (real-time)
- Running Tasks: 1/1
- Hourly Cost: $0.01245
- Daily Cost: $0.2988
- Monthly Cost: $8.96
- Idle Tasks: 0

### 2. Metrics Publishing Starts Automatically
First metrics publish: Immediately (Lambda runs after deployment)
Subsequent publishes: Every 15 minutes (automated)

### 3. CloudWatch Logs Track Everything
```
/aws/lambda/voice-bot-mvp-metrics-publisher
```
View to verify metrics publishing is working.

---

## Architecture

```
EventBridge (Every 15 min)
         ↓
    Lambda Function
    (Metrics Publisher)
         ↓
    ECS Service (Get config)
    CloudWatch API (Publish metrics)
         ↓
    CloudWatch Custom Metrics
    (voicebot/operations namespace)
         ↓
    CloudWatch Dashboard
    (14 widgets, real-time display)
```

**No manual tasks needed anywhere.**

---

## Verify It's Working

### Method 1: Check Dashboard
1. Go to CloudWatch console (ap-south-1)
2. Dashboards > `voice-bot-mvp-operations`
3. All widgets should show data
4. Cost values should match: $0.01245/hour

### Method 2: Check Metrics
1. CloudWatch > Metrics > Custom Namespaces
2. Look for: `voicebot/operations`
3. Should see 4 metrics: HourlyCost, DailyCost, MonthlyCost, IdleTasks
4. Each should have recent data points

### Method 3: Check Lambda Logs
1. CloudWatch > Log Groups
2. Look for: `/aws/lambda/voice-bot-mvp-metrics-publisher`
3. Should see recent log entries (from last 15 min)
4. Look for: "[SUCCESS] Metrics published to CloudWatch"

---

## Troubleshooting

### Problem: Dashboard shows "No data"
**Solution:**
1. Wait 5 minutes for first metrics to publish
2. Refresh dashboard (F5)
3. Check Lambda logs for errors

### Problem: Lambda function keeps failing
**Solution:**
1. Check CloudWatch logs: `/aws/lambda/voice-bot-mvp-metrics-publisher`
2. Verify AWS credentials: `aws sts get-caller-identity`
3. Verify region: ap-south-1

### Problem: Cost values incorrect
**Solution:**
1. Verify ECS config: 256 CPU, 512 MB memory
2. Check calculation: (0.25 × $0.0408) + (0.5 × $0.00450) = $0.01245/hour
3. Verify region: ap-south-1 (correct pricing used)

---

## Files Deployed (What Terraform Creates)

1. **CloudWatch Dashboard**
   - Resource: `aws_cloudwatch_dashboard.pm_operations`
   - Terraform file: `infra/terraform/dashboard.tf`

2. **Lambda Function**
   - Resource: `aws_lambda_function.metrics_publisher`
   - Code file: `infra/terraform/lambda_metrics.py`
   - Archive: `infra/terraform/lambda_metrics.zip` (created automatically)

3. **EventBridge Rule**
   - Resource: `aws_cloudwatch_event_rule.metrics_schedule`
   - Trigger: Every 15 minutes

4. **IAM Roles**
   - Resource: `aws_iam_role.lambda_metrics_role`
   - Policy: All necessary ECS & CloudWatch permissions

---

## Cost Tracking

### Current Monthly Cost
```
ECS Fargate:              $8.96
CloudWatch Dashboard:     Free (3 dashboards included)
Custom Metrics:           $0.40 (4 metrics × $0.10)
Lambda executions:        ~$0.10 (96 per day × $0.00000167)
EventBridge rules:        Free (first 10 free/month)
─────────────────────────────
Total Additional Cost:    ~$0.50/month
```

**Your monitoring costs:** Almost nothing

---

## For Senior PM Oversight

### What You Can See
✅ Real-time resource utilization (CPU, Memory)
✅ Cost tracking (hourly, daily, monthly)
✅ Task health and idle detection
✅ Service events and errors
✅ 24-hour trend history

### What You Can Decide
✅ Whether to scale up (based on utilization)
✅ Whether to use Fargate Spot (50% cost savings)
✅ Whether to optimize down (if under-utilized)
✅ When to add alarms/notifications

### What We Automated
✅ Dashboard creation
✅ Metrics calculation
✅ Metrics publishing
✅ Scheduling
✅ Log tracking

---

## Security & Best Practices

✅ **No hardcoded secrets** - Uses AWS IAM roles
✅ **Least privilege** - Lambda has minimal ECS/CloudWatch permissions
✅ **Fully managed** - No servers to maintain
✅ **Audit trail** - All actions logged in CloudWatch
✅ **Cost optimized** - Minimal Lambda executions (only every 15 min)

---

## Integration With Phase 0

This monitoring dashboard supports Phase 0 goals:
- **Cost Control:** Track spend automatically
- **Resource Optimization:** See utilization in real-time
- **Operational Visibility:** Monitor health automatically
- **MVP Validation:** Dashboard ready before phase completion

---

## What NOT Included (Optional Future)

❌ Email/Slack alerts (can add later)
❌ Forecasting (can add later)
❌ Custom anomaly detection (can add later)
❌ Grafana/Prometheus (not needed, CloudWatch is sufficient)

All of these can be added later without touching the current setup.

---

## Rollback (If Needed)

```powershell
cd infra
terraform destroy
```

This removes:
- Dashboard
- Lambda function
- EventBridge rule
- IAM roles

**Takes ~30 seconds**

---

## One-Time Setup Complete

After running `deploy-dashboard.ps1`:
1. Dashboard is live
2. Metrics publish automatically every 15 minutes
3. No further manual configuration needed
4. Monitor via CloudWatch console

Everything is **fully automated, production-ready, and hands-off**.

---

## Next Steps (After Deployment)

**Day 1:**
- Run deployment script
- Verify dashboard loads
- Check metrics appear

**Week 1:**
- Monitor trends
- Understand utilization patterns
- Decide on scaling (if needed)

**Ongoing:**
- Check dashboard weekly
- Monitor cost trends
- Share URL with team if needed

---

## Summary

**Option A (Manual CloudWatch - Previous):**
- 30 minutes of manual clicking
- Manual metrics scheduling
- PowerShell task scheduler setup

**Option B Upgraded (Fully Automated - Current):**
- ✅ 5 minutes to deploy (one command)
- ✅ Lambda replaces manual scheduling
- ✅ Dashboard created by code
- ✅ Everything infrastructure-as-code
- ✅ Enterprise-ready solution

**For a Senior PM:** This is the right approach. Deploy once, monitor forever.

---

## Ready to Deploy?

```powershell
.\deploy-dashboard.ps1
```

**That's all you need to do.**
