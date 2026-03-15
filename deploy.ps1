param(
    [switch]$Help
)

if ($Help) {
    Write-Host "Senior PM Dashboard Deployment"
    Write-Host "Usage: .\deploy.ps1"
    exit 0
}

Write-Host ""
Write-Host "SENIOR PM MONITORING DASHBOARD - DEPLOYMENT" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1] Checking AWS CLI..."
$aws = aws --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS CLI not found" -ForegroundColor Red
    Write-Host "Install from: https://aws.amazon.com/cli/" -ForegroundColor Yellow
    exit 1
}
Write-Host "OK - AWS CLI found" -ForegroundColor Green

Write-Host ""
Write-Host "[2] Checking Terraform..."
$tf = terraform -version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform not found" -ForegroundColor Red
    Write-Host "Install from: https://www.terraform.io/downloads" -ForegroundColor Yellow
    exit 1
}
Write-Host "OK - Terraform found" -ForegroundColor Green

Write-Host ""
Write-Host "[3] Checking AWS Credentials..."
$creds = aws sts get-caller-identity 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS credentials not configured" -ForegroundColor Red
    Write-Host "Run: aws configure" -ForegroundColor Yellow
    exit 1
}
Write-Host "OK - AWS credentials valid" -ForegroundColor Green

Write-Host ""
Write-Host "[4] Deploying infrastructure..."
Push-Location infra

Write-Host "Initializing Terraform..." -ForegroundColor Yellow
terraform init
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform init failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Planning deployment..." -ForegroundColor Yellow
terraform plan -out=tfplan
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform plan failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Applying infrastructure..." -ForegroundColor Yellow
terraform apply tfplan
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform apply failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "SUCCESS! Dashboard deployed!" -ForegroundColor Green
Write-Host ""
Write-Host "Your dashboard is now live!" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard URL:" -ForegroundColor Cyan
Write-Host "https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=voice-bot-mvp-operations" -ForegroundColor Gray
Write-Host ""

Pop-Location
Write-Host "Deployment complete!" -ForegroundColor Green
