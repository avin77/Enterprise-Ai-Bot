#!/usr/bin/env pwsh
# ECS Service Control Script (PowerShell)
# Stop/Start the voice-bot-mvp service to save costs

param(
    [ValidateSet('start', 'stop', 'status', 'toggle')]
    [string]$Action = 'status'
)

$CLUSTER = "voice-bot-mvp-cluster"
$SERVICE = "voice-bot-mvp-svc"
$REGION = "ap-south-1"

function Print-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Print-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Get-ServiceStatus {
    try {
        $response = aws ecs describe-services `
            --cluster $CLUSTER `
            --services $SERVICE `
            --region $REGION `
            --query 'services[0].[runningCount,desiredCount,status]' `
            --output json | ConvertFrom-Json

        $running = $response[0]
        $desired = $response[1]
        $status = $response[2]

        return @{
            Running = $running
            Desired = $desired
            Status = $status
        }
    }
    catch {
        Print-Error "Failed to get service status: $_"
        exit 1
    }
}

function Stop-Service {
    Print-Status "Stopping ECS service..."

    try {
        aws ecs update-service `
            --cluster $CLUSTER `
            --service $SERVICE `
            --desired-count 0 `
            --region $REGION | Out-Null

        Print-Status "Service scaled to 0 tasks. Service is now stopped."
        Print-Status "Cost is now: $0/hour"
    }
    catch {
        Print-Error "Failed to stop service: $_"
        exit 1
    }
}

function Start-Service {
    Print-Status "Starting ECS service..."

    try {
        aws ecs update-service `
            --cluster $CLUSTER `
            --service $SERVICE `
            --desired-count 1 `
            --region $REGION | Out-Null

        Print-Status "Service scaled to 1 task. Service is starting..."
        Print-Status "This will take 30-60 seconds to fully start"
    }
    catch {
        Print-Error "Failed to start service: $_"
        exit 1
    }
}

function Show-Status {
    Print-Status "Current service status:"
    Write-Host "Cluster: $CLUSTER" -ForegroundColor Cyan
    Write-Host "Service: $SERVICE" -ForegroundColor Cyan

    $svc = Get-ServiceStatus
    Write-Host "Running Tasks: $($svc.Running)" -ForegroundColor Cyan
    Write-Host "Desired Tasks: $($svc.Desired)" -ForegroundColor Cyan
    Write-Host "Status: $($svc.Status)" -ForegroundColor Cyan
}

# Main logic
switch ($Action) {
    'stop' { Stop-Service }
    'start' { Start-Service }
    'status' { Show-Status }
    'toggle' {
        $svc = Get-ServiceStatus
        if ($svc.Running -eq 0) {
            Print-Status "Service is stopped. Starting it..."
            Start-Service
        }
        else {
            Print-Status "Service is running. Stopping it..."
            Stop-Service
        }
    }
    default {
        Write-Host "Usage: $($MyInvocation.MyCommand.Name) {start|stop|status|toggle}" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Yellow
        Write-Host "  pwsh ecs-control.ps1 stop    # Stop the service (save costs)"
        Write-Host "  pwsh ecs-control.ps1 start   # Start the service"
        Write-Host "  pwsh ecs-control.ps1 status  # Check current status"
        Write-Host "  pwsh ecs-control.ps1 toggle  # Toggle between start/stop"
        exit 1
    }
}
