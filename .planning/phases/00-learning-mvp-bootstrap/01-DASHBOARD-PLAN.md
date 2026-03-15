# Senior PM Monitoring Dashboard - Implementation Plan

**Option:** B (Hybrid - Manual Dashboard + Custom Metrics)
**Status:** PLANNING
**Estimated Duration:** 30-45 minutes
**Date:** 2026-03-09

---

## Overview

Build a comprehensive senior PM dashboard in AWS CloudWatch with:
1. **Manual Dashboard** (CloudWatch console, click-based)
2. **Custom Metrics** (Python script publishing to CloudWatch)
3. **Cost Tracking** (Real-time cost estimation)
4. **Idle Task Detection** (Tasks running > 2 days)

---

## Phase 1: Custom Metrics Python Script

### What It Does
Runs every 15 minutes to:
- Calculate current hourly/daily/monthly cost
- Detect tasks running > 2 days
- Calculate resource efficiency score
- Publish to CloudWatch custom metrics

### Output Metrics to CloudWatch
```
voicebot/operations/hourly-cost         (USD)
voicebot/operations/daily-cost          (USD)
voicebot/operations/monthly-cost        (USD)
voicebot/operations/idle-tasks          (count)
voicebot/operations/resource-efficiency (%)
voicebot/operations/memory-efficiency   (%)
voicebot/operations/cpu-efficiency      (%)
```

### Files to Create
- `infra/scripts/publish_metrics.py` - Main script
- `infra/scripts/metrics-scheduler.ps1` - Windows Task Scheduler setup (or cron for Linux)

---

## Phase 2: Manual Dashboard Setup (CloudWatch Console)

### Dashboard Sections (What to create manually)

#### Section 1: Status & Health (2x2 grid)
```
┌─────────────────┬──────────────────┐
│  CPU Usage (%)  │  Memory Usage (%) │
│  [Line Chart]   │  [Line Chart]    │
├─────────────────┼──────────────────┤
│  Running Tasks  │  Task Status     │
│  [Number: 1]    │  [Gauge/Status]  │
└─────────────────┴──────────────────┘
```

#### Section 2: Cost Dashboard (2x2 grid)
```
┌─────────────────┬──────────────────┐
│ Hourly Cost     │ Daily Cost       │
│ [Number: 0.007] │ [Number: 0.17]   │
├─────────────────┼──────────────────┤
│ Monthly Cost    │ Cost Trend       │
│ [Number: 5.50]  │ [Line Chart]     │
└─────────────────┴──────────────────┘
```

#### Section 3: Task Monitoring (3-col grid)
```
┌──────────────────┬──────────────────┬──────────────────┐
│ Idle Tasks (>2d) │ Task Uptime      │ Task Health      │
│ [Number: 0]      │ [Number]         │ [Status Widget]  │
└──────────────────┴──────────────────┴──────────────────┘
```

#### Section 4: Logs & Insights (Full width)
```
┌─────────────────────────────────────────────────────────┐
│ Recent Errors & Events (CloudWatch Logs Insights)       │
│ [Query Results Table]                                   │
└─────────────────────────────────────────────────────────┘
```

### Manual Steps
1. Go to CloudWatch Console
2. Create new dashboard: "voice-bot-mvp-operations"
3. Add widgets manually (14 total)
4. Select metrics from ECS namespace + custom metrics
5. Save dashboard

---

## Phase 3: Schedule Custom Metrics Publishing

### Option A: Windows (Recommended for you)
- Use PowerShell Task Scheduler
- Run `publish_metrics.py` every 15 minutes
- Script: `infra/scripts/metrics-scheduler.ps1`

### Option B: Linux/Lambda (Alternative)
- Lambda function triggered by EventBridge every 15 min
- Same Python script

### Setup Steps
1. Create scheduled task in Windows Task Scheduler
2. Task: Run `python3 infra/scripts/publish_metrics.py`
3. Frequency: Every 15 minutes
4. Credentials: Use AWS IAM credentials from .aws/credentials

---

## Phase 4: Documentation & Phase Update

### Files to Update
- `.planning/phases/00-learning-mvp-bootstrap/00-CONTEXT.md` - Add dashboard section
- `.planning/phases/00-learning-mvp-bootstrap/00-UAT.md` - Add dashboard validation
- `infra/MONITORING-SETUP.md` - Add manual dashboard guide
- `RESOURCE-OPTIMIZATION-SUMMARY.md` - Add dashboard access info

---

## Implementation Steps (Execution Order)

### Step 1: Create Python Script (10 min)
```
📄 Create: infra/scripts/publish_metrics.py
- Import boto3 for CloudWatch
- Get ECS task info (running count, task ages)
- Calculate costs (CPU/Memory rates × current config)
- Publish custom metrics
- Handle errors gracefully
```

### Step 2: Setup Metric Publishing Schedule (5 min)
```
📋 Create: infra/scripts/metrics-scheduler.ps1
- Register Windows Task Scheduler job
- Run python script every 15 min
- Log output for debugging
```

### Step 3: Create Manual Dashboard (15 min)
```
🎨 Manual CloudWatch Steps:
1. Open AWS CloudWatch Console (ap-south-1)
2. Create Dashboard → Name: "voice-bot-mvp-operations"
3. Add 14 widgets following Section structure above
4. Select ECS metrics + custom metrics
5. Configure time ranges (24h, 7d, 30d)
6. Save & share URL
```

### Step 4: Validate & Document (5 min)
```
✅ Verify:
- Custom metrics appearing in CloudWatch
- Dashboard loading all widgets
- Cost calculations correct
- Idle task detection working
📝 Document dashboard URL
```

### Step 5: Update Phase Plan (5 min)
```
📝 Update documentation:
- Add dashboard sections to phase context
- Add validation steps to UAT
- Document metric definitions
```

---

## Success Criteria

### Metrics Publishing ✅
- [ ] Custom metrics visible in CloudWatch
- [ ] Data publishing every 15 minutes
- [ ] Cost calculations correct (match manual calc)
- [ ] Idle task detection working

### Dashboard ✅
- [ ] Dashboard loads without errors
- [ ] All 14 widgets showing data
- [ ] Cost values match metric calculations
- [ ] Timezone correct (IST for ap-south-1)

### Accessibility ✅
- [ ] Senior PM can access dashboard via URL
- [ ] Read-only IAM access configured
- [ ] Mobile-friendly (responsive)
- [ ] Documentation clear

---

## Estimated Costs (What Dashboard Will Show)

**Current Configuration:**
- CPU: 256 units (0.25 vCPU)
- Memory: 512 MB
- Region: ap-south-1
- Launch Type: FARGATE (Regular)

**Cost Calculation:**
```
Fargate CPU:    0.25 vCPU × $0.0408/hour = $0.0102/hour
Fargate Memory: 0.5 GB × $0.00450/hour   = $0.0023/hour
─────────────────────────────────────────────────
Total per hour:                          $0.0125/hour
Per day (24h):                           $0.30/day
Per month (30d):                         $9.00/month
```

**With custom metrics**, dashboard will show real cost data.

---

## Rollback Plan

If issues occur:
1. Stop metrics publishing: Delete scheduled task
2. Dashboard remains in CloudWatch (manual deletion needed)
3. No code/infrastructure changes, easy to recover

---

## Notes

- **Fargate Spot:** NOT changing yet (user preference)
- **Terraform:** Only for metrics script deployment (no Fargate changes)
- **IAM:** Uses existing AWS credentials
- **Region:** ap-south-1 (Mumbai) - all dashboards in this region

---

## Next Steps

1. ✅ Approval: User confirms "Option B"
2. ⏭️ Execute Phase 1: Create metrics script
3. ⏭️ Execute Phase 2: Create manual dashboard
4. ⏭️ Execute Phase 3: Schedule publishing
5. ⏭️ Execute Phase 4: Update documentation

---

**Ready to execute?** Press proceed to start Phase 1.
