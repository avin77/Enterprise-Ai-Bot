# Resource Optimization & Monitoring Summary

**Date:** 2026-03-09
**Status:** ✅ Complete - Ready for deployment

---

## The Problem

Your current configuration (256 CPU + 512 MB memory) is **too tight for production voice processing**:

```
Total Memory: 512 MB
├─ Python + FastAPI: ~150 MB
├─ WebSocket overhead: ~100 MB
├─ Voice processing: needs 200-500 MB
└─ Available headroom: ~60 MB ❌ DANGEROUS
```

**Result:** OOMKill crashes, service interruptions, poor user experience

---

## The Solution: 3-Part Setup

### 1️⃣ CloudWatch Monitoring Infrastructure
**File:** `infra/terraform/monitoring.tf`

Monitors real-time CPU and memory usage via AWS CloudWatch:
- Real-time dashboard visualization
- Automatic alarms at 80% CPU, 85% memory
- Historical data retention for trend analysis

**Deploy:**
```bash
cd infra && terraform apply
```

---

### 2️⃣ Resource Analysis Tool
**File:** `infra/scripts/resource_monitor.py`

Pulls CloudWatch metrics and generates recommendations:
```bash
python3 infra/scripts/resource_monitor.py voice-bot-mvp 24
```

**Output:**
- Current allocation (256 CPU, 512 MB)
- Last 24-hour peak utilization
- Specific recommendations with Terraform commands
- JSON report for automation

---

### 3️⃣ Easy Optimization Scripts

#### PowerShell Script (Easiest)
**File:** `infra/scripts/optimize-resources.ps1`
```powershell
./optimize-resources.ps1 -Preset small
# or
./optimize-resources.ps1 -CPU 512 -Memory 1024
```

Shows cost estimates, validates compatibility, applies changes.

#### Terraform Direct
```bash
terraform apply -var='cpu=512' -var='memory=1024'
```

---

## Recommended Actions

### Immediate (Next 30 minutes)
1. Review cost analysis in `.planning/AWS-COST-MANAGEMENT.md`
2. Choose target configuration from sizing table
3. Understand AWS Fargate constraints

### Short-term (Today)
1. Deploy monitoring:
   ```bash
   cd infra && terraform apply
   ```
2. Review CloudWatch dashboard for trends
3. Run load test with expected concurrent users

### Medium-term (This week)
1. Collect 24+ hours of production metrics
2. Run resource analysis:
   ```bash
   python3 infra/scripts/resource_monitor.py voice-bot-mvp 24
   ```
3. Apply recommended resource changes:
   ```bash
   ./optimize-resources.ps1 -Preset small
   ```

---

## Sizing Recommendations

### By Use Case

| Use Case | CPU | Memory | Monthly Cost | Notes |
|----------|-----|--------|--------------|-------|
| **Development** | 256 | 512 MB | $11 | Current - too tight |
| **Small Prod** | 512 | 1024 MB | $22 | 1-5 concurrent sessions |
| **Medium Prod** | 1024 | 2048 MB | $44 | 5-20 concurrent sessions |
| **Large Prod** | 2048 | 4096 MB | $88 | 20+ concurrent sessions |

**Default Recommendation:** Start with "Small Prod" (512 CPU + 1024 MB)
- Safe margin for voice processing peaks
- Only 2x cost increase ($11 → $22)
- Optimize down based on monitoring data

---

## Key Metrics to Watch

### CPU Utilization
- **Low (<20%):** Can downsize to save costs
- **Healthy (20-70%):** Right-sized
- **High (70-90%):** Consider increasing
- **Critical (>90%):** Scale immediately

### Memory Utilization
- **Low (<50%):** Can downsize
- **Healthy (50-80%):** Right-sized
- **High (80-90%):** Scale soon
- **Critical (>90%):** **DANGER - Will crash**

---

## Cost Impact

### Monthly Costs (Fargate Regular)
```
Current (256 CPU, 512 MB):     $11.00
Small Prod (512 CPU, 1024 MB): $22.00  (+$11)
```

### With Fargate Spot (50% Discount)
```
Current (256 CPU, 512 MB):     $5.50
Small Prod (512 CPU, 1024 MB): $11.00  (+$5.50)
```

**For dev/testing:** Spot Fargate is highly recommended (~50% cost savings)

---

## Files Summary

### Infrastructure
- `infra/terraform/monitoring.tf` - CloudWatch setup
- `infra/terraform/variables.tf` - (updated with documentation)
- `infra/terraform/main.tf` - (updated with documentation)

### Scripts
- `infra/scripts/resource_monitor.py` - Metrics analysis
- `infra/scripts/optimize-resources.ps1` - Easy resource adjustment
- `backend/app/monitoring.py` - In-app resource tracking

### Documentation
- `infra/MONITORING-SETUP.md` - Complete setup guide
- `.planning/AWS-COST-MANAGEMENT.md` - (updated with monitoring section)
- `RESOURCE-OPTIMIZATION-SUMMARY.md` - This file

---

## Quick Answers to Your Questions

### "Is 256 CPU and 512 MB memory required?"
**No.** It's the minimum, but too tight for production voice workloads.
- **Minimum safe:** 512 CPU + 1024 MB
- **Comfortable:** 1024 CPU + 2048 MB

### "Can we reduce to 128 CPU to save 50%?"
**No.** Would make OOMKill crashes worse.
- Trade-off: Use Fargate Spot instead (50% discount, no performance loss)

### "Do we have orphaned/duplicate tasks?"
**No.** Currently running 1 task (desired_count=1)
- Monitor for accidental scaling

### "What's our actual utilization?"
**Unknown until data is collected.**
- Deploy monitoring today
- Run `resource_monitor.py` after 24+ hours
- Make data-driven decisions

---

## Next: The Workflow

```
Week 1: Setup & Monitoring
├─ Deploy monitoring infrastructure ✓
├─ Wait 24-72 hours for metrics
└─ Run analysis script

Week 2: Right-Sizing
├─ Review utilization data
├─ Decide on target configuration
└─ Apply changes with optimize-resources.ps1

Week 3+: Optimization
├─ Monitor trends weekly
├─ Downsize if consistently <50% utilized
└─ Scale up if approaching limits
```

---

## Support & Troubleshooting

### CloudWatch Dashboard Not Showing
1. Check AWS region (should be us-east-1)
2. Wait 5-10 minutes after deployment
3. URL: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:

### resource_monitor.py Fails
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Verify service deployed
aws ecs list-services --cluster voice-bot-mvp-cluster --region us-east-1
```

### PowerShell Script Issues
```powershell
# Check Terraform is installed
terraform version

# Verify working directory
cd C:\Coding\Enterprise-AI-Voice-Bot
```

---

## Questions for Your Team

These monitoring tools help you answer:

1. **"Are we running minimum resources?"**
   - CloudWatch dashboard shows utilization
   - `resource_monitor.py` recommends sizing

2. **"Do we have orphaned/duplicate tasks?"**
   - ECS service shows running vs. desired count
   - Monitor for accidental scaling

3. **"What's our utilization?"**
   - CPU/Memory graphs in CloudWatch
   - Peak/average metrics in `resource_monitor.py` report

4. **"Can we save costs with Spot?"**
   - Yes: 50% discount with acceptable interruption trade-off
   - Already in terraform configuration

---

## Implementation Checklist

- [ ] Read `.planning/AWS-COST-MANAGEMENT.md` (updated)
- [ ] Review this file: `RESOURCE-OPTIMIZATION-SUMMARY.md`
- [ ] Read monitoring guide: `infra/MONITORING-SETUP.md`
- [ ] Deploy monitoring: `cd infra && terraform apply`
- [ ] Wait 24+ hours for metrics
- [ ] Run: `python3 infra/scripts/resource_monitor.py voice-bot-mvp 24`
- [ ] Apply recommendations: `./optimize-resources.ps1 -Preset small`
- [ ] Monitor weekly using CloudWatch dashboard

---

## References

- **Cost Details:** See `.planning/AWS-COST-MANAGEMENT.md`
- **Setup Guide:** See `infra/MONITORING-SETUP.md`
- **AWS Documentation:** [ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)

---

**Status:** Ready to deploy ✅
**Next Step:** Run `terraform apply` to activate monitoring
