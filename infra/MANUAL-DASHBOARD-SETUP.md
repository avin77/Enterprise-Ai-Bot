# Senior PM CloudWatch Dashboard - Manual Setup Guide

**Time Required:** 15-20 minutes
**Region:** ap-south-1 (Mumbai)
**Status:** Ready to create

---

## Dashboard Overview

This dashboard provides senior PM visibility into:
- Real-time resource utilization (CPU, Memory)
- Cost tracking (hourly, daily, monthly)
- Task health and idle detection
- Error logs and events

**Final Dashboard URL:** `https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=voice-bot-mvp-operations`

---

## Step 1: Create Dashboard

1. **Open CloudWatch Console**
   - URL: https://console.aws.amazon.com/cloudwatch/
   - Select Region: **ap-south-1** (Mumbai)

2. **Navigate to Dashboards**
   - Left menu → **Dashboards**
   - Click **Create dashboard**

3. **Name the Dashboard**
   - Dashboard name: `voice-bot-mvp-operations`
   - Click **Create dashboard**

4. **Select "Edit Mode"**
   - Dashboard appears empty
   - You'll add widgets in steps below

---

## Step 2: Add Resource Health Widgets (Row 1)

### 2.1: CPU Utilization (Line Chart)

1. Click **Add widget** → **Line**
2. Search: `CPUUtilization`
3. Select: `AWS/ECS`
4. Dimensions:
   - ServiceName: `voice-bot-mvp-svc`
   - ClusterName: `voice-bot-mvp-cluster`
5. Configure:
   - Title: `CPU Utilization (%)`
   - Stat: `Average`
   - Period: `1 minute`
   - Time range: `Last 24 hours`
6. Click **Create widget**

### 2.2: Memory Utilization (Line Chart)

1. Click **Add widget** → **Line**
2. Search: `MemoryUtilization`
3. Select: `AWS/ECS`
4. Dimensions: Same as above (ServiceName, ClusterName)
5. Configure:
   - Title: `Memory Utilization (%)`
   - Stat: `Average`
   - Period: `1 minute`
   - Time range: `Last 24 hours`
6. Click **Create widget**

### 2.3: Running Tasks (Number Widget)

1. Click **Add widget** → **Number**
2. Search: `RunningCount`
3. Select: `AWS/ECS`
4. Dimensions: Same as above
5. Configure:
   - Title: `Running Tasks`
   - Stat: `Average`
6. Click **Create widget**

### 2.4: Task Status (Number Widget)

1. Click **Add widget** → **Number**
2. Search: `DesiredTaskCount`
3. Select: `AWS/ECS`
4. Dimensions: Same as above
5. Configure:
   - Title: `Desired Tasks`
   - Stat: `Average`
6. Click **Create widget**

---

## Step 3: Add Cost Widgets (Row 2)

**Note:** These use custom metrics published by `publish_metrics.py`

### 3.1: Hourly Cost (Number Widget)

1. Click **Add widget** → **Number**
2. In search, type custom metric name: `HourlyCost`
3. Select: Custom namespace `voicebot/operations`
4. Configure:
   - Title: `Hourly Cost (USD)`
   - Stat: `Average`
   - Period: `1 minute`
   - Format: Show 4 decimal places
5. Click **Create widget**

### 3.2: Daily Cost (Number Widget)

1. Click **Add widget** → **Number**
2. Metric: `DailyCost`
3. Namespace: `voicebot/operations`
4. Configure:
   - Title: `Daily Cost (USD)`
   - Stat: `Average`
   - Format: Show 2 decimal places
5. Click **Create widget**

### 3.3: Monthly Cost (Number Widget)

1. Click **Add widget** → **Number**
2. Metric: `MonthlyCost`
3. Namespace: `voicebot/operations`
4. Configure:
   - Title: `Monthly Cost (USD)`
   - Stat: `Average`
   - Format: Show 2 decimal places
5. Click **Create widget**

### 3.4: Cost Trend (Line Chart)

1. Click **Add widget** → **Line**
2. Metrics: Select all three (HourlyCost, DailyCost, MonthlyCost)
3. Configure:
   - Title: `Cost Trend (24h)`
   - Time range: `Last 24 hours`
   - Period: `5 minutes`
4. Click **Create widget**

---

## Step 4: Add Task Monitoring Widgets (Row 3)

### 4.1: Idle Tasks (Number Widget)

1. Click **Add widget** → **Number**
2. Metric: `IdleTasks`
3. Namespace: `voicebot/operations`
4. Configure:
   - Title: `Idle Tasks (>48h)`
   - Stat: `Maximum`
5. Click **Create widget**
6. **Interpretation:**
   - 0 = Good (no old tasks)
   - >0 = Alert (old tasks should be stopped)

### 4.2: Task Count History (Line Chart)

1. Click **Add widget** → **Line**
2. Search: `RunningCount`
3. Select: `AWS/ECS`
4. Configure:
   - Title: `Task Count History`
   - Stat: `Average`
   - Period: `5 minutes`
   - Time range: `Last 24 hours`
5. Click **Create widget**

### 4.3: Service Status (Table)

1. Click **Add widget** → **Logs table**
2. Log Group: `/ecs/voice-bot-mvp`
3. Query:
   ```
   fields @timestamp, @message, container_name
   | filter container_name = "backend"
   | stats count() as errors by bin(5m)
   ```
4. Configure:
   - Title: `Service Events (5m)`
   - Columns: Show timestamp, count
5. Click **Create widget**

---

## Step 5: Add Logs & Insights (Row 4)

### 5.1: Recent Errors (Logs Widget)

1. Click **Add widget** → **Logs table**
2. Log Group: `/ecs/voice-bot-mvp`
3. Query:
   ```
   fields @timestamp, @message
   | filter @message like /ERROR|Exception|Failed/
   | sort @timestamp desc
   | limit 20
   ```
4. Configure:
   - Title: `Recent Errors`
5. Click **Create widget**

### 5.2: Memory Spikes (Logs Insights)

1. Click **Add widget** → **Logs Insights**
2. Log Group: `/ecs/voice-bot-mvp`
3. Query:
   ```
   fields @timestamp, @duration
   | filter @duration > 1000
   | stats max(@duration) as max_duration, count() by bin(1h)
   ```
4. Configure:
   - Title: `Processing Time Trend`
5. Click **Create widget**

---

## Step 6: Arrange & Save

1. **Arrange Widgets**
   - Drag widgets to organize in rows
   - Recommended layout:
     ```
     Row 1: CPU | Memory | Running | Desired
     Row 2: HrCost | DayCost | MonCost | CostTrend
     Row 3: IdleTasks | TaskHistory | Events
     Row 4: Recent Errors | ProcessingTime (full width)
     ```

2. **Save Dashboard**
   - Click **Save dashboard** button
   - Dashboard name: `voice-bot-mvp-operations`
   - Click **Save**

3. **Verify**
   - Dashboard should now display all metrics
   - Metrics may show "No data" if script hasn't run yet

---

## Step 7: Verify Metrics Are Publishing

1. **Run metrics script manually**
   ```powershell
   cd infra/scripts
   python publish_metrics.py
   ```

2. **Check CloudWatch**
   - Refresh dashboard
   - Look for custom metrics appearing in widgets

3. **Verify data appears**
   - CPU/Memory: Should show values immediately
   - Cost: Should show after metrics script runs
   - Idle Tasks: Should show 0 (no old tasks)

---

## Dashboard Interpretation Guide

### CPU & Memory Widgets
- **Green (Low):** < 30% - Good utilization
- **Yellow (Good):** 30-70% - Right-sized
- **Red (High):** 70-90% - Monitor closely
- **Critical:** > 90% - Action needed

### Cost Widgets
- **Hourly:** ~$0.0125 (current config)
- **Daily:** ~$0.30
- **Monthly:** ~$9.00
- *Formula:* (CPU vCPU × $0.0408) + (Memory GB × $0.0045)

### Idle Tasks Widget
- **0:** ✓ No old tasks (good)
- **>0:** ⚠ Old tasks running (stop them)
- Check: "Idle Tasks (>48h)" = tasks running > 2 days

### Task Count
- **Desired:** Should match desired_count in ECS service
- **Running:** Should equal desired
- Mismatch = Deployment issue

---

## Troubleshooting

### Custom Metrics Not Appearing

**Problem:** Cost metrics showing "No data"
**Solution:**
1. Run metrics script: `python infra/scripts/publish_metrics.py`
2. Wait 1-2 minutes for CloudWatch to process
3. Refresh dashboard

### Wrong Values

**Problem:** Cost showing wrong amount
**Solution:**
1. Verify AWS region: Should be **ap-south-1**
2. Check script output: `python infra/scripts/publish_metrics.py`
3. Verify CPU/Memory in ECS service matches calculations

### Missing ECS Metrics

**Problem:** CPU/Memory showing "No data"
**Solution:**
1. Verify service is running: `aws ecs list-services --cluster voice-bot-mvp-cluster --region ap-south-1`
2. Verify correct service name: `voice-bot-mvp-svc`
3. CloudWatch needs 5 min of data before showing

---

## Scheduled Updates

Once dashboard is created, metrics will update automatically:
- **ECS Metrics (CPU, Memory, Tasks):** Every 1 minute
- **Custom Metrics (Cost, Idle Tasks):** Every 15 minutes
- **Logs:** As soon as they're written

---

## Cost of Dashboard

- **CloudWatch Dashboards:** Free (3 dashboards included)
- **Custom Metrics:** $0.10/metric/month
  - You'll have 4 custom metrics × $0.10 = $0.40/month
- **Total Additional Cost:** ~$0.40/month

---

## Next Steps

1. ✅ Create dashboard (this guide)
2. ✅ Setup metrics scheduler: `./infra/scripts/setup-metrics-scheduler.ps1`
3. ✅ Run metrics script once to verify
4. ✅ Monitor dashboard weekly
5. Share dashboard URL with team

---

## Dashboard Sharing

Once created, share with team:

**View-Only Link:**
```
https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=voice-bot-mvp-operations
```

**Sharing Steps:**
1. Open dashboard
2. Click **Share dashboard**
3. Create read-only access URL
4. Share with team

---

## Reference: Widget Configuration

| Widget | Type | Metric | Namespace |
|--------|------|--------|-----------|
| CPU | Line | CPUUtilization | AWS/ECS |
| Memory | Line | MemoryUtilization | AWS/ECS |
| Running | Number | RunningCount | AWS/ECS |
| Desired | Number | DesiredTaskCount | AWS/ECS |
| HrCost | Number | HourlyCost | voicebot/operations |
| DayCost | Number | DailyCost | voicebot/operations |
| MonCost | Number | MonthlyCost | voicebot/operations |
| IdleTasks | Number | IdleTasks | voicebot/operations |

---

**Total Setup Time:** 15-20 minutes
**Status:** Ready to follow guide
