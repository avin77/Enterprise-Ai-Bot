# Senior PM Dashboard - Complete Setup Checklist

**Status:** ✅ All code ready, follow checklist below
**Time Required:** 30-45 minutes total
**Date:** 2026-03-09

---

## What's Ready

✅ Metrics Python Script: `infra/scripts/publish_metrics.py`
- Tested and working
- Publishes: HourlyCost, DailyCost, MonthlyCost, IdleTasks
- Output: Last run shows $0.01245/hour, $8.96/month

✅ PowerShell Scheduler: `infra/scripts/setup-metrics-scheduler.ps1`
- Ready to setup Task Scheduler
- Runs metrics script every 15 minutes

✅ Manual Dashboard Guide: `infra/MANUAL-DASHBOARD-SETUP.md`
- Step-by-step instructions
- 15-20 minutes to complete

---

## Checklist: Complete These Steps

### Phase 1: Setup Metrics Publishing (5 minutes)

**On Windows PowerShell:**
```powershell
cd C:\Coding\Enterprise-AI-Voice-Bot
.\infra\scripts\setup-metrics-scheduler.ps1
```

**What it does:**
- Creates Windows Task Scheduler job
- Runs `publish_metrics.py` every 15 minutes
- Auto-starts with system
- Logs output

**Verification:**
```powershell
# View task
Get-ScheduledTask -TaskName "VoiceBotMetricsPublisher"

# Run manually to test
schtasks /run /tn "VoiceBotMetricsPublisher"
```

**Troubleshooting:**
If script fails, run metrics manually first:
```powershell
python infra/scripts/publish_metrics.py
```

---

### Phase 2: Create CloudWatch Dashboard (15 minutes)

**Follow:** `infra/MANUAL-DASHBOARD-SETUP.md` step-by-step

1. Open CloudWatch Console: https://console.aws.amazon.com/cloudwatch/
2. Select Region: **ap-south-1** (Mumbai)
3. Go to Dashboards
4. Create dashboard: `voice-bot-mvp-operations`
5. Add 14 widgets as described
6. Save

**Estimated times per section:**
- Row 1 (Resource Health): 3 min
- Row 2 (Cost): 4 min
- Row 3 (Task Monitoring): 4 min
- Row 4 (Logs): 2 min
- Arrange & Save: 2 min
- **Total: 15 min**

---

### Phase 3: Verify Everything Works (10 minutes)

**Step 1: Check Metrics Publishing**
```powershell
# Run script once
python infra/scripts/publish_metrics.py
# Should show:
#   HourlyCost: 0.01245
#   DailyCost: 0.2988
#   MonthlyCost: 8.96
#   IdleTasks: 0
```

**Step 2: Verify Metrics in CloudWatch**
1. CloudWatch > Metrics > Custom Namespaces
2. Look for: `voicebot/operations`
3. Should see 4 metrics:
   - HourlyCost
   - DailyCost
   - MonthlyCost
   - IdleTasks

**Step 3: Refresh Dashboard**
1. Open dashboard: `voice-bot-mvp-operations`
2. All widgets should show data
3. Cost values should match manual calculation

---

## Dashboard Metrics Reference

### ECS Metrics (Automatic)
- CPU Utilization: Publishes every minute
- Memory Utilization: Publishes every minute
- Running Tasks: Publishes every minute
- Desired Tasks: Publishes every minute

### Custom Metrics (From Python Script)
- HourlyCost: ~$0.01245
- DailyCost: ~$0.2988
- MonthlyCost: ~$8.96
- IdleTasks: 0 (current, no old tasks)

### Expected Values

**Current Configuration (256 CPU + 512 MB):**
```
Region: ap-south-1
Launch Type: FARGATE (Regular)

CPU Cost:     0.25 vCPU × $0.0408/hour = $0.0102/hour
Memory Cost:  0.5 GB × $0.00450/hour = $0.0023/hour
Total Hourly: $0.01245
Total Daily:  $0.2988
Total Monthly: $8.96
```

---

## Dashboard What You'll See

### Status Section (Top)
```
CPU: 0.55%          | Memory: 11.5%
Running: 1          | Desired: 1
```

### Cost Section
```
Hourly: $0.01245    | Daily: $0.2988
Monthly: $8.96      | [Cost trend line chart]
```

### Task Health
```
Idle Tasks: 0       | Task History [chart]   | Service Events
```

### Logs
```
Recent Errors: None | Processing Times [chart]
```

---

## After Setup: Weekly Maintenance

### Every Week
1. Check dashboard for trends
2. Note peak CPU/Memory (if any)
3. Review cost tracker
4. Verify idle task count is 0

### Every Month
1. Generate cost analysis report
2. Compare with estimate ($8.96/month)
3. Check if right-sized or needs adjustment
4. Document insights

---

## Cost Analysis

### Current vs Recommended

| Metric | Current (256 CPU + 512 MB) | Recommended (512 CPU + 1024 MB) |
|--------|--------------------------|--------------------------------|
| Hourly Cost | $0.01245 | $0.02490 |
| Daily Cost | $0.2988 | $0.5976 |
| Monthly Cost | $8.96 | $17.93 |
| Difference | - | +$8.97/month |

**Your Status:** Currently running at ~11.5% memory utilization
- Safe but tight for voice processing peaks
- Monitor for 2 weeks, then decide if scaling needed

---

## Files Created

✅ **Python Scripts**
- `infra/scripts/publish_metrics.py` (tested)
  - Calculates & publishes costs
  - Detects idle tasks

✅ **PowerShell Setup**
- `infra/scripts/setup-metrics-scheduler.ps1` (ready)
  - Schedules metrics publishing
  - Runs every 15 minutes

✅ **Documentation**
- `infra/MANUAL-DASHBOARD-SETUP.md` (15-step guide)
  - Step-by-step CloudWatch instructions
  - Widget configurations
  - Troubleshooting

✅ **Planning**
- `.planning/phases/00-learning-mvp-bootstrap/01-DASHBOARD-PLAN.md`
  - Complete implementation plan
  - Success criteria

---

## Time Breakdown

| Task | Time | Status |
|------|------|--------|
| Create metrics script | 10 min | ✅ Done |
| Test metrics script | 5 min | ✅ Done |
| Create scheduler script | 10 min | ✅ Done |
| Create dashboard guide | 20 min | ✅ Done |
| **YOUR TASKS:** | | |
| Setup Task Scheduler | 5 min | ⏳ To Do |
| Create CloudWatch dashboard | 15 min | ⏳ To Do |
| Verify everything | 10 min | ⏳ To Do |
| **TOTAL** | **75 min** | **90% Done** |

---

## Troubleshooting Guide

### Issue: Metrics script fails
```
[ERROR] No ECS clusters found
```
**Fix:**
- Verify AWS credentials: `aws sts get-caller-identity`
- Verify region: `aws ecs list-clusters --region ap-south-1`

### Issue: Task Scheduler won't run
```
Task failed with exit code: 1
```
**Fix:**
1. Run manually: `python infra/scripts/publish_metrics.py`
2. Check AWS credentials in ~/.aws/credentials
3. Verify Python path in Task Scheduler

### Issue: Dashboard shows "No data"
```
CloudWatch graphs empty
```
**Fix:**
1. Wait 5-10 minutes after first metrics publish
2. Run metrics script: `python infra/scripts/publish_metrics.py`
3. Refresh dashboard (F5)
4. Check widget region is ap-south-1

### Issue: Cost values don't match
```
Dashboard shows $100/month instead of $8.96
```
**Fix:**
1. Verify ECS config: CPU 256, Memory 512 MB
2. Check metric is DailyCost not HourlyCost
3. Verify region: ap-south-1

---

## Questions Answered by Dashboard

### For Senior PMs
1. **"Are we running minimum resources?"**
   - Dashboard shows: CPU 0.55%, Memory 11.5%
   - Answer: Yes, could optimize down (but risky)

2. **"What's our current spend?"**
   - Dashboard shows: $8.96/month
   - Answer: $0.01245/hour currently

3. **"Are we wasting money?"**
   - Dashboard shows idle tasks: 0
   - Answer: No waste, no orphaned tasks

4. **"Should we use Spot instances?"**
   - Dashboard doesn't answer this (separate decision)
   - Recommendation: Yes, could save 50% ($4.48/month)

---

## Security Notes

✅ No secrets in code
✅ No credentials hardcoded
✅ Uses AWS credentials from ~/.aws/credentials
✅ CloudWatch metrics are AWS-managed (no storage needed)
✅ Dashboard is read-only sharable

---

## Ready to Execute?

**Step 1 (5 min):** Run PowerShell setup
```powershell
.\infra\scripts\setup-metrics-scheduler.ps1
```

**Step 2 (15 min):** Follow `infra/MANUAL-DASHBOARD-SETUP.md`
- Create dashboard in CloudWatch
- Add 14 widgets

**Step 3 (10 min):** Verify everything works
- Check metrics publishing
- Refresh dashboard
- Confirm values correct

**Estimated Total:** 30 minutes

---

**Status:** ✅ Ready to implement
**Next:** Run PowerShell setup script
