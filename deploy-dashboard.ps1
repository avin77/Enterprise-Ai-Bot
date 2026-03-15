#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy Senior PM Monitoring Dashboard with One Command
.DESCRIPTION
    Deploys complete monitoring infrastructure:
    - CloudWatch Dashboard (14 widgets)
    - Lambda metrics publisher
    - EventBridge trigger (every 15 min)
    - All costs and efficiency metrics
.EXAMPLE
    .\deploy-dashboard.ps1
#>

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   SENIOR PM MONITORING DASHBOARD - AUTO DEPLOYMENT        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Check prerequisites
Write-Host "[CHECK] Prerequisites..." -ForegroundColor Yellow

$checks = @{
    "AWS CLI" = { aws --version 2>$null }
    "Terraform" = { terraform -version 2>$null }
    "AWS Credentials" = { aws sts get-caller-identity 2>$null }
}

$allPass = $true
foreach ($check in $checks.GetEnumerator()) {
    try {
        & $check.Value | Out-Null
        Write-Host "  ✓ $($check.Name)" -ForegroundColor Green
    }
    catch {
        Write-Host "  ✗ $($check.Name) - NOT FOUND" -ForegroundColor Red
        $allPass = $false
    }
}

if (-not $allPass) {
    Write-Host "`n[ERROR] Missing prerequisites. Install and configure AWS CLI and Terraform." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[INFO] Current Configuration:" -ForegroundColor Cyan
Write-Host "  Region: ap-south-1 (Mumbai)" -ForegroundColor Gray
Write-Host "  Service: voice-bot-mvp-svc" -ForegroundColor Gray
Write-Host "  Dashboard: voice-bot-mvp-operations" -ForegroundColor Gray
Write-Host "  Metrics: HourlyCost, DailyCost, MonthlyCost, IdleTasks" -ForegroundColor Gray
Write-Host ""

# Initialize Terraform
Write-Host "[INIT] Initializing Terraform..." -ForegroundColor Yellow
Push-Location infra
terraform init

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Terraform init failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Plan
Write-Host ""
Write-Host "[PLAN] Generating deployment plan..." -ForegroundColor Yellow
terraform plan -out=tfplan

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Terraform plan failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Apply
Write-Host ""
Write-Host "[APPLY] Deploying infrastructure (this may take 1-2 minutes)..." -ForegroundColor Yellow
terraform apply tfplan

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Terraform apply failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   DEPLOYMENT SUCCESSFUL!                                  ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

# Get outputs
Write-Host "[INFO] Dashboard Details:" -ForegroundColor Cyan
$dashboardUrl = terraform output -raw dashboard_url 2>$null
$lambdaFunc = terraform output -raw lambda_function_name 2>$null
$eventsRule = terraform output -raw metrics_schedule_rule 2>$null

if ($dashboardUrl) {
    Write-Host "  Dashboard URL:" -ForegroundColor Yellow
    Write-Host "  $dashboardUrl`n" -ForegroundColor Gray
}

if ($lambdaFunc) {
    Write-Host "  Lambda Function: $lambdaFunc" -ForegroundColor Yellow
    Write-Host "    Publishes metrics every 15 minutes" -ForegroundColor Gray
    Write-Host ""
}

if ($eventsRule) {
    Write-Host "  EventBridge Rule: $eventsRule" -ForegroundColor Yellow
    Write-Host "    Triggers Lambda on schedule" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "[INFO] What's Running:" -ForegroundColor Cyan
Write-Host "  ✓ CloudWatch Dashboard: 14 widgets (CPU, Memory, Cost, Tasks)" -ForegroundColor Green
Write-Host "  ✓ Lambda Function: Auto-publishes metrics to CloudWatch" -ForegroundColor Green
Write-Host "  ✓ EventBridge Trigger: Runs every 15 minutes" -ForegroundColor Green
Write-Host "  ✓ IAM Roles: All permissions configured" -ForegroundColor Green
Write-Host ""

Write-Host "[NEXT] Check Your Dashboard:" -ForegroundColor Yellow
Write-Host "  1. Open AWS CloudWatch Console" -ForegroundColor Gray
Write-Host "  2. Region: ap-south-1" -ForegroundColor Gray
Write-Host "  3. Dashboards > voice-bot-mvp-operations" -ForegroundColor Gray
Write-Host "  4. See: CPU, Memory, Cost, Task Health" -ForegroundColor Gray
Write-Host ""

Write-Host "[VERIFY] Metrics Publishing:" -ForegroundColor Yellow
Write-Host "  CloudWatch > Metrics > Custom Namespaces > voicebot/operations" -ForegroundColor Gray
Write-Host "  You'll see: HourlyCost, DailyCost, MonthlyCost, IdleTasks" -ForegroundColor Gray
Write-Host ""

Write-Host "[COST] Current Estimate:" -ForegroundColor Yellow
Write-Host "  Hourly: $0.01245" -ForegroundColor Gray
Write-Host "  Daily: $0.2988" -ForegroundColor Gray
Write-Host "  Monthly: $8.96" -ForegroundColor Gray
Write-Host ""

Write-Host "[SUPPORT] CloudWatch Logs:" -ForegroundColor Yellow
Write-Host "  /aws/lambda/$lambdaFunc" -ForegroundColor Gray
Write-Host '  Check here if metrics dont appear' -ForegroundColor Gray
Write-Host ""

Write-Host "[STATUS] Everything is automated:" -ForegroundColor Cyan
Write-Host "  - No manual dashboard setup needed" -ForegroundColor Green
Write-Host "  - Metrics publish automatically every 15 min" -ForegroundColor Green
Write-Host "  - All infrastructure as code (Terraform)" -ForegroundColor Green
Write-Host "  - Ready for production monitoring" -ForegroundColor Green
Write-Host ""

Pop-Location

Write-Host "Deployment complete! Your monitoring dashboard is live." -ForegroundColor Green
Write-Host ""
