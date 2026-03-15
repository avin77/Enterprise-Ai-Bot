#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Easy resource optimization for ECS Fargate voice bot
.DESCRIPTION
    Helps you quickly adjust CPU and memory allocation based on monitoring data
.EXAMPLE
    ./optimize-resources.ps1 -Preset "production"
    ./optimize-resources.ps1 -CPU 512 -Memory 1024
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "small", "medium", "large", "custom")]
    [string]$Preset = "custom",

    [Parameter(Mandatory=$false)]
    [ValidateSet(256, 512, 1024, 2048, 4096)]
    [int]$CPU,

    [Parameter(Mandatory=$false)]
    [int]$Memory
)

# Preset configurations
$presets = @{
    "dev" = @{CPU = 256; Memory = 512; Description = "Development/Testing (tight)" }
    "small" = @{CPU = 512; Memory = 1024; Description = "Small Production (1-5 concurrent)" }
    "medium" = @{CPU = 1024; Memory = 2048; Description = "Medium Production (5-20 concurrent)" }
    "large" = @{CPU = 2048; Memory = 4096; Description = "Large Production (20+ concurrent)" }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "ECS Fargate Resource Optimizer" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Apply preset if not custom
if ($Preset -ne "custom") {
    $config = $presets[$Preset]
    $CPU = $config.CPU
    $Memory = $config.Memory
    Write-Host "Preset: $($config.Description)" -ForegroundColor Green
}
else {
    if (-not $CPU -or -not $Memory) {
        Write-Host "❓ Resource Options:`n" -ForegroundColor Yellow
        foreach ($key in $presets.Keys) {
            $p = $presets[$key]
            Write-Host "  $key`: $($p.Description)" -ForegroundColor Gray
            Write-Host "    └─ CPU: $($p.CPU), Memory: $($p.Memory) MB`n" -ForegroundColor Gray
        }
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  ./optimize-resources.ps1 -Preset production`n" -ForegroundColor Gray
        Write-Host "  ./optimize-resources.ps1 -CPU 512 -Memory 1024`n" -ForegroundColor Gray
        exit 1
    }
}

# Validate CPU/Memory compatibility (AWS Fargate constraints)
$validCombos = @{
    256  = @(512, 1024, 2048)
    512  = @(1024, 2048, 3072, 4096)
    1024 = @(2048, 3072, 4096, 5120, 6144, 7168, 8192)
    2048 = @(4096, 5120, 6144, 7168, 8192, 9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384)
    4096 = @(8192, 9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384, 17408, 18432, 19456, 20480, 21504, 22528, 23552, 24576, 25600, 26624, 27648, 28672, 29696, 30720)
}

if (-not $validCombos[$CPU] -or $Memory -notin $validCombos[$CPU]) {
    Write-Host "❌ Invalid CPU/Memory combination!" -ForegroundColor Red
    Write-Host "  CPU: $CPU, Memory: $Memory`n" -ForegroundColor Red
    Write-Host "Valid combinations for CPU=$CPU:" -ForegroundColor Yellow
    if ($validCombos[$CPU]) {
        Write-Host "  Memory: $($validCombos[$CPU] -join ', ') MB`n" -ForegroundColor Gray
    }
    exit 1
}

# Calculate costs
$cpuPrice = 0.04048  # USD per vCPU-hour
$memPrice = 0.004445 # USD per GB-hour
$cpuVcpu = $CPU / 1024
$memGb = $Memory / 1024
$hourlyRate = ($cpuVcpu * $cpuPrice) + ($memGb * $memPrice)
$dailyCost = $hourlyRate * 24
$monthlyCost = $dailyCost * 30

Write-Host "📊 New Configuration:" -ForegroundColor Green
Write-Host "  CPU:     $CPU units ($cpuVcpu vCPU)" -ForegroundColor Green
Write-Host "  Memory:  $Memory MB ($memGb GB)" -ForegroundColor Green
Write-Host ""
Write-Host "💰 Estimated Costs (Fargate Regular, us-east-1):" -ForegroundColor Cyan
Write-Host "  Hourly:  `$$($hourlyRate.ToString('F4'))" -ForegroundColor Cyan
Write-Host "  Daily:   `$$($dailyCost.ToString('F2'))" -ForegroundColor Cyan
Write-Host "  Monthly: `$$($monthlyCost.ToString('F2'))" -ForegroundColor Cyan
Write-Host ""
Write-Host "  With Spot (50% discount): `$$($monthlyCost * 0.5 | % {$_.ToString('F2')})/month" -ForegroundColor Green

# Show deployment command
Write-Host "`n📋 To Apply Changes:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Option 1: Terraform command" -ForegroundColor Gray
Write-Host "    cd infra && terraform apply -var='cpu=$CPU' -var='memory=$Memory'" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Option 2: Update deploy.ps1" -ForegroundColor Gray
Write-Host "    Change: -Cpu $CPU -Memory $Memory" -ForegroundColor Cyan
Write-Host ""

# Ask for confirmation
$response = Read-Host "⚡ Apply these changes? (y/n)"
if ($response -eq 'y') {
    Write-Host ""
    Write-Host "Running Terraform apply..." -ForegroundColor Yellow
    Push-Location "infra"
    terraform apply -var="cpu=$CPU" -var="memory=$Memory" -auto-approve
    Pop-Location

    Write-Host "`n✅ Resources updated!" -ForegroundColor Green
    Write-Host "Monitor progress at: https://console.aws.amazon.com/ecs/" -ForegroundColor Cyan
}
else {
    Write-Host "`n⏭️  No changes applied." -ForegroundColor Gray
}

Write-Host ""
