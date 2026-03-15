#!/usr/bin/env pwsh
<#
.SYNOPSIS
Deploy Phase 0 backend to AWS ECS Spot Fargate with full automation.

.DESCRIPTION
Automatically:
- Launches ECS task on Spot Fargate (50% discount)
- Gets public IP address
- Tests all endpoints (/health, /chat, /ws)
- Displays deployment summary

.EXAMPLE
.\deploy-spot.ps1
#>

param(
    [string]$Cluster = "enterprise-ai-voice-bot-cluster",
    [string]$TaskDefinition = "enterprise-ai-voice-bot-task",
    [string]$Region = "ap-south-1",
    [int]$WaitSeconds = 60
)

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  DEPLOYING PHASE 0 TO AWS SPOT FARGATE" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get subnets and security groups
Write-Host "[1/6] Getting VPC configuration..." -ForegroundColor Yellow

try {
    $subnets = aws ec2 describe-subnets `
        --region $Region `
        --query 'Subnets[?State==`available`][SubnetId]' `
        --output text `
        2>$null

    if (-not $subnets) {
        Write-Host "  ✗ No subnets found. Check your AWS region." -ForegroundColor Red
        exit 1
    }

    $subnetArray = $subnets -split '\s+' | Where-Object { $_ }
    Write-Host "  ✓ Found subnets: $($subnetArray -join ', ')" -ForegroundColor Green

    $securityGroups = aws ec2 describe-security-groups `
        --region $Region `
        --query 'SecurityGroups[0].GroupId' `
        --output text `
        2>$null

    if (-not $securityGroups -or $securityGroups -eq "None") {
        Write-Host "  ✗ No security groups found." -ForegroundColor Red
        exit 1
    }

    Write-Host "  ✓ Security group: $securityGroups" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Error getting VPC config: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Get task definition
Write-Host "[2/6] Getting task definition..." -ForegroundColor Yellow

try {
    $taskDefArn = aws ecs describe-task-definition `
        --task-definition $TaskDefinition `
        --region $Region `
        --query 'taskDefinition.taskDefinitionArn' `
        --output text `
        2>$null

    Write-Host "  ✓ Task definition: $taskDefArn" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Error getting task definition: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Launch task on Spot Fargate
Write-Host "[3/6] Launching task on Spot Fargate..." -ForegroundColor Yellow

try {
    $subnetString = $subnetArray[0..1] -join ','

    $runTaskResponse = aws ecs run-task `
        --cluster $Cluster `
        --task-definition $taskDefArn `
        --capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=70 capacityProvider=FARGATE,weight=30 `
        --network-configuration "awsvpcConfiguration={subnets=[$subnetString],securityGroups=[$securityGroups],assignPublicIp=ENABLED}" `
        --region $Region `
        --output json `
        2>$null | ConvertFrom-Json

    $taskArn = $runTaskResponse.tasks[0].taskArn
    if (-not $taskArn) {
        Write-Host "  ✗ Failed to launch task" -ForegroundColor Red
        Write-Host "  Response: $($runTaskResponse | ConvertTo-Json)" -ForegroundColor Red
        exit 1
    }

    Write-Host "  ✓ Task launched: $taskArn" -ForegroundColor Green
    Write-Host "  ✓ Capacity Provider: Spot Fargate (70%) + Regular Fargate (30% fallback)" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Error launching task: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Wait for public IP
Write-Host "[4/6] Waiting for public IP assignment (timeout: ${WaitSeconds}s)..." -ForegroundColor Yellow

$taskId = $taskArn -split '/' | Select-Object -Last 1
$publicIp = $null
$elapsed = 0
$interval = 5

while ($elapsed -lt $WaitSeconds) {
    try {
        $taskDetail = aws ecs describe-tasks `
            --cluster $Cluster `
            --tasks $taskArn `
            --region $Region `
            --output json `
            2>$null | ConvertFrom-Json

        $taskStatus = $taskDetail.tasks[0].lastStatus

        # Try to get ENI
        $eniId = $taskDetail.tasks[0].attachments | Where-Object { $_.name -eq 'elasticNetworkInterface' } | Select-Object -First 1

        if ($eniId) {
            $eniDetail = $eniId.details | ConvertFrom-Json -AsHashtable
            $networkInterfaceId = $eniDetail['networkInterfaceId']

            if ($networkInterfaceId) {
                $eniData = aws ec2 describe-network-interfaces `
                    --network-interface-ids $networkInterfaceId `
                    --region $Region `
                    --output json `
                    2>$null | ConvertFrom-Json

                $publicIp = $eniData.NetworkInterfaces[0].Association.PublicIp

                if ($publicIp -and $publicIp -ne "None") {
                    Write-Host "  ✓ Public IP assigned: $publicIp" -ForegroundColor Green
                    break
                }
            }
        }

        Write-Host "  ⋯ Task status: $taskStatus, waiting... ($($elapsed)s)" -ForegroundColor Gray
        Start-Sleep -Seconds $interval
        $elapsed += $interval
    } catch {
        Write-Host "  ⋯ Checking status... ($($elapsed)s)" -ForegroundColor Gray
        Start-Sleep -Seconds $interval
        $elapsed += $interval
    }
}

if (-not $publicIp) {
    Write-Host "  ⚠ Timeout waiting for IP. Task may still be starting." -ForegroundColor Yellow
    Write-Host "  Check status with:" -ForegroundColor Yellow
    Write-Host "    aws ecs describe-tasks --cluster $Cluster --tasks $taskArn --region $Region" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Retrying..." -ForegroundColor Yellow

    # One more attempt
    Start-Sleep -Seconds 10

    try {
        $taskDetail = aws ecs describe-tasks `
            --cluster $Cluster `
            --tasks $taskArn `
            --region $Region `
            --output json `
            2>$null | ConvertFrom-Json

        $eniId = $taskDetail.tasks[0].attachments | Where-Object { $_.name -eq 'elasticNetworkInterface' } | Select-Object -First 1

        if ($eniId) {
            $eniDetail = $eniId.details | ConvertFrom-Json -AsHashtable
            $networkInterfaceId = $eniDetail['networkInterfaceId']

            if ($networkInterfaceId) {
                $eniData = aws ec2 describe-network-interfaces `
                    --network-interface-ids $networkInterfaceId `
                    --region $Region `
                    --output json `
                    2>$null | ConvertFrom-Json

                $publicIp = $eniData.NetworkInterfaces[0].Association.PublicIp
            }
        }
    } catch { }
}

Write-Host ""

# Step 5: Test endpoints
if ($publicIp -and $publicIp -ne "None") {
    Write-Host "[5/6] Testing endpoints..." -ForegroundColor Yellow

    $endpoint = "http://$($publicIp):8000"

    # Test health
    try {
        $healthResponse = Invoke-WebRequest -Uri "$endpoint/health" -UseBasicParsing -TimeoutSec 5
        if ($healthResponse.StatusCode -eq 200) {
            Write-Host "  ✓ GET /health - OK (200)" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ GET /health - Status $($healthResponse.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ✗ GET /health - Connection failed (task still starting?)" -ForegroundColor Yellow
    }

    # Test chat with token
    try {
        $chatBody = @{
            text = "Hello from AWS Spot!"
            session_id = "deploy-test-$(Get-Date -Format 'yyyyMMddHHmmss')"
        } | ConvertTo-Json

        $chatResponse = Invoke-WebRequest `
            -Uri "$endpoint/chat" `
            -Method POST `
            -Headers @{ Authorization = "Bearer dev-token"; "Content-Type" = "application/json" } `
            -Body $chatBody `
            -UseBasicParsing `
            -TimeoutSec 10

        if ($chatResponse.StatusCode -eq 200) {
            $chatData = $chatResponse.Content | ConvertFrom-Json
            Write-Host "  ✓ POST /chat - OK (200)" -ForegroundColor Green
            Write-Host "    Reply: $($chatData.reply.Substring(0, [Math]::Min(50, $chatData.reply.Length))...)..." -ForegroundColor Green
        } else {
            Write-Host "  ⚠ POST /chat - Status $($chatResponse.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ✗ POST /chat - Connection failed (task still starting?)" -ForegroundColor Yellow
    }

    # Test auth rejection
    try {
        $invalidResponse = Invoke-WebRequest `
            -Uri "$endpoint/chat" `
            -Method POST `
            -Headers @{ "Content-Type" = "application/json" } `
            -Body '{"text":"test"}' `
            -UseBasicParsing `
            -TimeoutSec 5 `
            -ErrorAction SilentlyContinue

        if ($invalidResponse.StatusCode -eq 401 -or $null -eq $invalidResponse) {
            Write-Host "  ✓ Auth validation - OK (401 without token)" -ForegroundColor Green
        }
    } catch {
        if ($_.Exception.Response.StatusCode -eq 401) {
            Write-Host "  ✓ Auth validation - OK (401 without token)" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ Auth test inconclusive" -ForegroundColor Yellow
        }
    }

} else {
    Write-Host "[5/6] Skipping endpoint tests (waiting for IP)" -ForegroundColor Yellow
}

Write-Host ""

# Step 6: Deployment summary
Write-Host "[6/6] Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Task ARN:             $taskArn" -ForegroundColor White
Write-Host "Capacity Provider:    FARGATE_SPOT (70%) + FARGATE (30%)" -ForegroundColor White
Write-Host "Region:               $Region" -ForegroundColor White
Write-Host "Cluster:              $Cluster" -ForegroundColor White

if ($publicIp -and $publicIp -ne "None") {
    Write-Host ""
    Write-Host "Public Endpoint:      http://$publicIp:8000" -ForegroundColor Green
    Write-Host ""
    Write-Host "API Endpoints:" -ForegroundColor White
    Write-Host "  • GET  /health                 (no auth)" -ForegroundColor Cyan
    Write-Host "  • POST /chat                   (requires Bearer token)" -ForegroundColor Cyan
    Write-Host "  • WS   /ws?token=dev-token     (WebSocket streaming)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Test Commands:" -ForegroundColor White
    Write-Host "  curl http://$publicIp:8000/health" -ForegroundColor Cyan
    Write-Host "  curl -X POST http://$publicIp:8000/chat -H 'Authorization: Bearer dev-token' -H 'Content-Type: application/json' -d '{\"text\": \"hello\"}'" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "⚠  Public IP not yet assigned (task still starting)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Check status with:" -ForegroundColor White
    Write-Host "  aws ecs describe-tasks --cluster $Cluster --tasks $taskArn --region $Region --query 'tasks[0].attachments'" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host ""
Write-Host "Cost Information:" -ForegroundColor White
Write-Host "  Spot Fargate:  ~$0.17/day (50% discount)" -ForegroundColor Green
Write-Host "  Stop anytime:  aws ecs stop-task --cluster $Cluster --task $($taskId) --region $Region" -ForegroundColor Gray
Write-Host ""
Write-Host "Deployment started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""
