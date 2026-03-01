param(
    [string]$AwsRegion = "us-east-1",
    [string]$AwsProfile = "",
    [string]$AppName = "voice-bot-mvp",
    [string]$ImageTag = "latest",
    [switch]$DeployService = $false
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

if ($AwsProfile) {
    $env:AWS_PROFILE = $AwsProfile
}
$env:AWS_REGION = $AwsRegion

Invoke-Step "Checking required CLIs"
aws --version | Out-Null
terraform version | Out-Null
docker --version | Out-Null

$repoName = "$AppName-backend"

Invoke-Step "Ensure ECR repository exists"
try {
    $repoUri = aws ecr describe-repositories --repository-names $repoName --region $AwsRegion --query "repositories[0].repositoryUri" --output text
} catch {
    $repoUri = aws ecr create-repository --repository-name $repoName --region $AwsRegion --query "repository.repositoryUri" --output text
}

Invoke-Step "Build and push backend image"
docker build -f backend/Dockerfile -t "$AppName:$ImageTag" .
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin ($repoUri -replace "/$repoName$", "")
docker tag "$AppName:$ImageTag" "$repoUri`:$ImageTag"
docker push "$repoUri`:$ImageTag"

Invoke-Step "Apply Terraform bootstrap"
$deployVar = if ($DeployService) { "true" } else { "false" }
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply -auto-approve `
  -var "aws_region=$AwsRegion" `
  -var "app_name=$AppName" `
  -var "image_tag=$ImageTag" `
  -var "deploy_service=$deployVar"

Invoke-Step "Bootstrap complete"
Write-Host "Repository URL: $repoUri"

