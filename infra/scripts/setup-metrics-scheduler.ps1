#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup Windows Task Scheduler to publish metrics every 15 minutes
.DESCRIPTION
    Creates a scheduled task that runs publish_metrics.py every 15 minutes
    to update CloudWatch with cost and efficiency metrics
.EXAMPLE
    ./setup-metrics-scheduler.ps1
.NOTES
    Requires: AWS credentials configured in ~/.aws/credentials
    Region: ap-south-1 (hardcoded in script)
#>

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CloudWatch Metrics Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Configuration
$TaskName = "VoiceBotMetricsPublisher"
$ScriptPath = Join-Path $PSScriptRoot "publish_metrics.py"
$LogPath = Join-Path $PSScriptRoot "metrics-scheduler.log"
$PythonExe = "python"

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "[ERROR] Script not found: $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Script path: $ScriptPath" -ForegroundColor Gray
Write-Host "[INFO] Log path: $LogPath`n" -ForegroundColor Gray

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "[WARN] Task '$TaskName' already exists" -ForegroundColor Yellow
    $response = Read-Host "Replace existing task? (y/n)"
    if ($response -ne 'y') {
        Write-Host "[INFO] Cancelled." -ForegroundColor Gray
        exit 0
    }
    # Remove existing task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[INFO] Removed existing task`n" -ForegroundColor Gray
}

# Create action
$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument """$ScriptPath""" `
    -WorkingDirectory (Split-Path $ScriptPath)

# Create trigger (every 15 minutes, starting now)
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# Create principal (run with current user, no elevation needed)
$principal = New-ScheduledTaskPrincipal `
    -UserID "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Publish ECS metrics to CloudWatch every 15 minutes" `
        -Force | Out-Null

    Write-Host "[OK] Task registered: $TaskName" -ForegroundColor Green
    Write-Host "     Frequency: Every 15 minutes" -ForegroundColor Green
    Write-Host "     Start time: $(Get-Date -Format 'HH:mm:ss')`n" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Failed to register task: $_" -ForegroundColor Red
    exit 1
}

# Test by running once
Write-Host "[INFO] Running script once to verify setup...`n" -ForegroundColor Cyan
& $PythonExe $ScriptPath

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Task Details:" -ForegroundColor Yellow
Write-Host "  Name: $TaskName" -ForegroundColor Gray
Write-Host "  Script: $ScriptPath" -ForegroundColor Gray
Write-Host "  Frequency: Every 15 minutes" -ForegroundColor Gray
Write-Host ""

Write-Host "Management:" -ForegroundColor Yellow
Write-Host "  View task: tasklist /fi `"imagename eq TaskScheduler.exe`"" -ForegroundColor Gray
Write-Host "  Run manually: schtasks /run /tn `"$TaskName`"" -ForegroundColor Gray
Write-Host "  Disable: schtasks /change /tn `"$TaskName`" /disable" -ForegroundColor Gray
Write-Host "  Delete: schtasks /delete /tn `"$TaskName`" /f" -ForegroundColor Gray
Write-Host ""

Write-Host "Verify in CloudWatch:" -ForegroundColor Yellow
Write-Host "  1. Open AWS CloudWatch Console" -ForegroundColor Gray
Write-Host "  2. CloudWatch > Metrics > Custom Namespaces" -ForegroundColor Gray
Write-Host "  3. Look for namespace: voicebot/operations" -ForegroundColor Gray
Write-Host "  4. Metrics: HourlyCost, DailyCost, MonthlyCost, IdleTasks`n" -ForegroundColor Gray

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Verify AWS credentials in ~/.aws/credentials" -ForegroundColor Gray
Write-Host "  2. Metrics will publish automatically every 15 minutes" -ForegroundColor Gray
Write-Host "  3. Create dashboard (see MANUAL-DASHBOARD-SETUP.md)" -ForegroundColor Gray
Write-Host ""
