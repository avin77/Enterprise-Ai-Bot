# Infrastructure Monitoring & Resource Optimization Setup

This guide covers the monitoring infrastructure deployed to track resource utilization and optimize costs.

## Files Added

### Terraform
- **`infra/terraform/monitoring.tf`** - CloudWatch dashboards and alarms for CPU/memory monitoring

### Python Scripts
- **`infra/scripts/resource_monitor.py`** - Analyzes CloudWatch metrics and generates optimization recommendations
- **`backend/app/monitoring.py`** - In-application resource tracking (optional integration)

### PowerShell Scripts
- **`infra/scripts/optimize-resources.ps1`** - Easy resource adjustment with cost estimation

### Documentation
- **`.planning/AWS-COST-MANAGEMENT.md`** - Complete cost and resource sizing guide

## Quick Start

### 1. Deploy Monitoring Infrastructure

```bash
cd infra
terraform apply
```

This creates:
- CloudWatch dashboard for real-time metrics
- CloudWatch alarms (CPU > 80%, Memory > 85%)
- CloudWatch log group for metrics

### 2. Monitor Resource Usage

**Option A: AWS Console**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:
→ Find "voice-bot-mvp-resources" dashboard
→ Real-time CPU & memory graphs
```

**Option B: Command Line**
```bash
# Generate resource report (after 24+ hours of data)
python3 infra/scripts/resource_monitor.py voice-bot-mvp 24

# Output: current allocation, peak utilization, recommendations
# Example: CPU avg 25%, max 60% → Could downsize
```

### 3. Adjust Resources

**Option A: Easy PowerShell Script**
```powershell
# Interactive resource adjustment
./infra/scripts/optimize-resources.ps1 -Preset small
# or
./infra/scripts/optimize-resources.ps1 -CPU 512 -Memory 1024
```

**Option B: Direct Terraform**
```bash
cd infra
terraform apply -var='cpu=512' -var='memory=1024'
```

## Understanding Your Current Setup

### Current Allocation
- **CPU:** 256 units (0.25 vCPU)
- **Memory:** 512 MB
- **Monthly Cost:** ~$11 (regular Fargate), ~$5.50 (Spot)

### Is This Enough?

❌ **NO** for voice/audio processing production workloads

- Python runtime + FastAPI: ~150 MB
- Voice transcription peaks: 200-400 MB
- Voice synthesis peaks: 300-500 MB
- WebSocket connections: ~1 MB each
- **Risk:** OOMKill crashes, service interruptions

### Recommended Sizing

| Use Case | CPU | Memory | Cost/Month |
|----------|-----|--------|-----------|
| Development | 256 | 512 MB | $11 |
| Small Prod (1-5 concurrent) | 512 | 1024 MB | $22 |
| Medium Prod (5-20 concurrent) | 1024 | 2048 MB | $44 |
| Large Prod (20+ concurrent) | 2048 | 4096 MB | $88 |

## Monitoring Workflow

### Daily
1. Check CloudWatch dashboard for trends
2. Look for memory creeping toward 400 MB
3. Check if CPU ever maxes out

### Weekly
```bash
python3 infra/scripts/resource_monitor.py voice-bot-mvp 168
```
Review recommendations and adjust if needed

### Monthly
Run full analysis after significant traffic periods:
```bash
python3 infra/scripts/resource_monitor.py voice-bot-mvp 720
```

## CloudWatch Alarms

Two alarms trigger when resources get tight:

### CPU Utilization > 80%
- **Triggered when:** Average CPU > 80% for 10+ minutes
- **Means:** Service is CPU-constrained, increase CPU units
- **Action:** Scale up using `optimize-resources.ps1`

### Memory Utilization > 85%
- **Triggered when:** Average memory > 85% for 10+ minutes
- **Means:** Service is memory-constrained, increase memory
- **Action:** Scale up using `optimize-resources.ps1`

## In-App Monitoring (Optional)

To add real-time resource tracking to your API:

```python
# In backend/app/main.py
from backend.app.monitoring import log_startup_info, log_resource_snapshot

# At startup
log_startup_info()

# In WebSocket handler or endpoints
log_resource_snapshot("websocket_received")
```

Output:
```
[websocket_received] Resources - Mem: 245MB, CPU: 15%, Conn: 3
```

## Cost Optimization Tips

### Use Fargate Spot (50% Discount)
In deploy.ps1:
```powershell
# Change this:
# -LaunchType FARGATE
# To this:
-LaunchType FARGATE_SPOT
```

Savings: ~50% on compute costs
Trade-off: Tasks can be interrupted (acceptable for dev/staging)

### Auto-Scaling (Future)
When you need variable load handling:
```hcl
# In monitoring.tf
resource "aws_appautoscaling_target" "ecs" {
  min_capacity = 1
  max_capacity = 3
  # Scale based on CPU utilization
}
```

### Scheduled Shutdown (Development)
If you only need the service during business hours:
```bash
# Stop at 6 PM daily, start at 8 AM
# Saves ~$5/month on compute
```

## Troubleshooting

### "No data available" in metrics
- Service was just deployed (wait 5-10 minutes)
- Service has very low traffic (metrics only publish with activity)
- CloudWatch data takes ~3 minutes to aggregate

### Dashboard not showing
- Dashboard created in CloudWatch
- Regional: Check you're in correct AWS region (us-east-1)
- URL: https://console.aws.amazon.com/cloudwatch/

### resource_monitor.py fails
```bash
# Ensure AWS credentials are configured
aws sts get-caller-identity

# Ensure service is deployed
aws ecs list-services --cluster voice-bot-mvp-cluster
```

## Questions to Ask Your Team

Based on this monitoring setup:

1. **"What's our typical concurrent session count?"**
   → Look at CloudWatch connection metrics

2. **"When does memory spike during voice processing?"**
   → Run load test and check dashboard

3. **"Should we use Fargate Spot?"**
   → Yes, if service can handle occasional interruptions (50% savings!)

4. **"Do we need auto-scaling?"**
   → Only if traffic varies 10x+ between peak/off-peak

## Next Steps

- [ ] Deploy monitoring: `terraform apply`
- [ ] Wait 24+ hours for data collection
- [ ] Run: `python3 infra/scripts/resource_monitor.py voice-bot-mvp 24`
- [ ] Review recommendations
- [ ] Adjust resources: `./optimize-resources.ps1 -Preset small`
- [ ] Monitor trends weekly

## Resources

- [AWS ECS Fargate Pricing](https://aws.amazon.com/ecs/pricing/)
- [CloudWatch Metrics Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/)
- [ECS Task CPU/Memory Constraints](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html)

---

**Added:** 2026-03-09
**Status:** Monitoring infrastructure ready for deployment
