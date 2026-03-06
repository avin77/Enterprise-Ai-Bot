<#
.SYNOPSIS
CLI-first AWS bootstrap for Phase-0 ECS/Fargate deploy and teardown.

.DESCRIPTION
Builds and pushes backend image to ECR, registers ECS task definition, and can
create/update an ECS service for smoke tests. Teardown mode removes short-lived
resources to minimize cost.
#>

[CmdletBinding()]
param(
    [ValidateSet("deploy", "teardown", "smoke")]
    [string]$Mode = "deploy",
    [string]$AwsRegion = "us-east-1",
    [string]$AwsProfile = "",
    [string]$AppName = "voice-bot-mvp",
    [string]$ImageTag = "latest",
    [int]$ContainerPort = 8000,
    [int]$Cpu = 256,
    [int]$Memory = 512,
    [int]$DesiredCount = 1,
    [string]$TaskRoleArn = "",
    [switch]$DeployService = $false,
    [string[]]$SubnetIds = @(),
    [string[]]$SecurityGroupIds = @(),
    [switch]$SkipImageBuild = $false,
    [switch]$DeleteRepository = $false
)

$ErrorActionPreference = "Stop"
# AWS CLI commands intentionally rely on $LASTEXITCODE checks for some
# first-run flows (for example ECR repository creation on not-found).
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Invoke-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not installed."
    }
}

function Invoke-AwsQuiet {
    param([scriptblock]$Command)
    $previousErrorAction = $ErrorActionPreference
    $output = $null
    $exitCode = 0
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Command 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    return [pscustomobject]@{
        Output   = $output
        ExitCode = $exitCode
    }
}

function Read-ListFromEnv {
    param([string[]]$Current, [string]$EnvName)
    if ($Current.Count -gt 0) {
        return $Current
    }
    $raw = [Environment]::GetEnvironmentVariable($EnvName)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @()
    }
    return $raw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

function To-NetworkConfigurationArg {
    param([string[]]$Subnets, [string[]]$SecurityGroups)
    if ($Subnets.Count -eq 0 -or $SecurityGroups.Count -eq 0) {
        throw "SubnetIds and SecurityGroupIds are required when running service/task in awsvpc mode."
    }
    $subnetsCsv = ($Subnets -join ",")
    $sgCsv = ($SecurityGroups -join ",")
    return "awsvpcConfiguration={subnets=[$subnetsCsv],securityGroups=[$sgCsv],assignPublicIp=ENABLED}"
}

function Ensure-ExecutionRoleArn {
    param([string]$RoleName)
    $roleLookup = Invoke-AwsQuiet { aws iam get-role --role-name $RoleName --query "Role.Arn" --output text }
    $arn = $roleLookup.Output
    if ($roleLookup.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($arn) -or $arn -eq "None") {
        Invoke-Step "Creating IAM execution role: $RoleName"
        $trustPolicy = @{
            Version = "2012-10-17"
            Statement = @(
                @{
                    Effect = "Allow"
                    Principal = @{ Service = "ecs-tasks.amazonaws.com" }
                    Action = "sts:AssumeRole"
                }
            )
        } | ConvertTo-Json -Depth 5 -Compress
        $policyPath = Join-Path $env:TEMP "$RoleName-trust-policy.json"
        Set-Content -Path $policyPath -Value $trustPolicy -Encoding Ascii
        aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$policyPath" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create IAM role '$RoleName'."
        }
        aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to attach execution policy to IAM role '$RoleName'."
        }
        Start-Sleep -Seconds 10
        $arn = aws iam get-role --role-name $RoleName --query "Role.Arn" --output text
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($arn) -or $arn -eq "None") {
            throw "Unable to resolve IAM role ARN for '$RoleName' after create."
        }
    }
    return $arn
}

function Ensure-EcrRepositoryUri {
    param([string]$RepositoryName, [string]$Region)
    $repoLookup = Invoke-AwsQuiet { aws ecr describe-repositories --repository-names $RepositoryName --region $Region --query "repositories[0].repositoryUri" --output text }
    $uri = $repoLookup.Output
    if ($repoLookup.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($uri) -or $uri -eq "None") {
        Invoke-Step "Creating ECR repository: $RepositoryName"
        $uri = aws ecr create-repository --repository-name $RepositoryName --region $Region --query "repository.repositoryUri" --output text
    }
    return $uri
}

function Ensure-EcsCluster {
    param([string]$ClusterName)
    $clusterLookup = Invoke-AwsQuiet { aws ecs describe-clusters --clusters $ClusterName --query "clusters[0].status" --output text }
    $status = $clusterLookup.Output
    if ($clusterLookup.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($status) -or $status -eq "None" -or $status -eq "INACTIVE") {
        Invoke-Step "Creating ECS cluster: $ClusterName"
        aws ecs create-cluster --cluster-name $ClusterName | Out-Null
    }
}

function Ensure-LogGroup {
    param([string]$LogGroupName)
    $logGroupLookup = Invoke-AwsQuiet { aws logs describe-log-groups --log-group-name-prefix $LogGroupName --query "logGroups[?logGroupName=='$LogGroupName'] | length(@)" --output text }
    $existing = $logGroupLookup.Output
    if ($logGroupLookup.ExitCode -ne 0 -or $existing -eq "0") {
        Invoke-Step "Creating CloudWatch log group: $LogGroupName"
        aws logs create-log-group --log-group-name $LogGroupName 2>$null | Out-Null
    }
}

function Register-TaskDefinition {
    param(
        [string]$Family,
        [string]$ImageUri,
        [string]$ExecutionRoleArn,
        [string]$RuntimeTaskRoleArn,
        [string]$LogGroupName,
        [int]$Port,
        [int]$TaskCpu,
        [int]$TaskMemory,
        [string]$Region
    )
    Invoke-Step "Registering ECS task definition"
    # Use Python script to avoid PowerShell JSON parameter passing issues
    $pythonScript = Join-Path $PSScriptRoot "aws_ecs_register.py"
    if (-not (Test-Path $pythonScript)) {
        throw "Python helper script not found: $pythonScript"
    }

    $taskDefArn = python "$pythonScript" `
        $Family `
        $ImageUri `
        $ExecutionRoleArn `
        $RuntimeTaskRoleArn `
        $LogGroupName `
        $Port `
        $TaskCpu `
        $TaskMemory `
        $Region

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($taskDefArn)) {
        throw "Failed to register ECS task definition for family '$Family'."
    }
    return $taskDefArn
}

function Ensure-Service {
    param(
        [string]$ClusterName,
        [string]$ServiceName,
        [string]$TaskDefinitionArn,
        [int]$Count,
        [string]$NetworkConfiguration
    )
    $serviceLookup = Invoke-AwsQuiet { aws ecs describe-services --cluster $ClusterName --services $ServiceName --query "services[0].status" --output text }
    $status = $serviceLookup.Output
    if ($serviceLookup.ExitCode -eq 0 -and $status -eq "ACTIVE") {
        Invoke-Step "Updating ECS service: $ServiceName"
        aws ecs update-service --cluster $ClusterName --service $ServiceName --task-definition $TaskDefinitionArn --desired-count $Count | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update ECS service '$ServiceName'."
        }
        return
    }

    Invoke-Step "Creating ECS service: $ServiceName"
    aws ecs create-service `
        --cluster $ClusterName `
        --service-name $ServiceName `
        --task-definition $TaskDefinitionArn `
        --launch-type FARGATE `
        --desired-count $Count `
        --network-configuration $NetworkConfiguration | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create ECS service '$ServiceName'."
    }
}

function Run-EphemeralTask {
    param(
        [string]$ClusterName,
        [string]$TaskDefinitionArn,
        [string]$NetworkConfiguration
    )
    Invoke-Step "Running one-off ECS task"
    return aws ecs run-task `
        --cluster $ClusterName `
        --launch-type FARGATE `
        --task-definition $TaskDefinitionArn `
        --count 1 `
        --network-configuration $NetworkConfiguration `
        --query "tasks[0].taskArn" `
        --output text
}

if ($AwsProfile) {
    $env:AWS_PROFILE = $AwsProfile
}
$env:AWS_REGION = $AwsRegion

$SubnetIds = Read-ListFromEnv -Current $SubnetIds -EnvName "AWS_SUBNET_IDS"
$SecurityGroupIds = Read-ListFromEnv -Current $SecurityGroupIds -EnvName "AWS_SECURITY_GROUP_IDS"

$clusterName = "$AppName-cluster"
$serviceName = "$AppName-svc"
$repositoryName = "$AppName-backend"
$taskFamily = "$AppName-task"
$logGroupName = "/ecs/$AppName"
$executionRoleName = "$AppName-task-execution-role"

Require-Command aws
if (-not $SkipImageBuild) {
    Require-Command docker
}

aws sts get-caller-identity --query "Account" --output text | Out-Null

if ($Mode -eq "teardown") {
    Invoke-Step "Starting teardown for $AppName ($AwsRegion)"
    $taskLookup = Invoke-AwsQuiet { aws ecs list-tasks --cluster $clusterName --query "taskArns[]" --output text }
    $taskArns = $taskLookup.Output
    if ($taskLookup.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($taskArns) -and $taskArns -ne "None") {
        foreach ($taskArn in ($taskArns -split "\s+" | Where-Object { $_ })) {
            aws ecs stop-task --cluster $clusterName --task $taskArn --reason "phase0 teardown" | Out-Null
        }
    }

    $serviceStatusLookup = Invoke-AwsQuiet { aws ecs describe-services --cluster $clusterName --services $serviceName --query "services[0].status" --output text }
    $svcStatus = $serviceStatusLookup.Output
    if ($serviceStatusLookup.ExitCode -eq 0 -and $svcStatus -eq "ACTIVE") {
        aws ecs delete-service --cluster $clusterName --service $serviceName --force | Out-Null
    }

    $clusterStatusLookup = Invoke-AwsQuiet { aws ecs describe-clusters --clusters $clusterName --query "clusters[0].status" --output text }
    $clusterStatus = $clusterStatusLookup.Output
    if ($clusterStatusLookup.ExitCode -eq 0 -and $clusterStatus -eq "ACTIVE") {
        aws ecs delete-cluster --cluster $clusterName | Out-Null
    }

    $logGroupStatusLookup = Invoke-AwsQuiet { aws logs describe-log-groups --log-group-name-prefix $logGroupName --query "logGroups[?logGroupName=='$logGroupName'] | length(@)" --output text }
    $hasLogGroup = $logGroupStatusLookup.Output
    if ($logGroupStatusLookup.ExitCode -eq 0 -and $hasLogGroup -ne "0") {
        aws logs delete-log-group --log-group-name $logGroupName 2>$null | Out-Null
    }

    if ($DeleteRepository) {
        aws ecr delete-repository --repository-name $repositoryName --region $AwsRegion --force 2>$null | Out-Null
    }

    $result = @{
        mode        = "teardown"
        aws_region  = $AwsRegion
        app_name    = $AppName
        cluster     = $clusterName
        service     = $serviceName
        repository  = $repositoryName
        deleted_ecr = [bool]$DeleteRepository
    }
    $result | ConvertTo-Json -Depth 4
    exit 0
}

Invoke-Step "Ensuring ECR repository and pushing image"
$repoUri = Ensure-EcrRepositoryUri -RepositoryName $repositoryName -Region $AwsRegion
if (-not $SkipImageBuild) {
    docker build -f backend/Dockerfile -t "${AppName}:$ImageTag" .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed for ${AppName}:$ImageTag. Ensure Docker Desktop/daemon is running."
    }
    aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin ($repoUri -replace "/$repositoryName$", "")
    if ($LASTEXITCODE -ne 0) {
        throw "Docker login to ECR failed for '$repoUri'."
    }
    docker tag "${AppName}:$ImageTag" "${repoUri}:$ImageTag"
    if ($LASTEXITCODE -ne 0) {
        throw "Docker tag failed for ${repoUri}:$ImageTag."
    }
    docker push "${repoUri}:$ImageTag"
    if ($LASTEXITCODE -ne 0) {
        throw "Docker push failed for ${repoUri}:$ImageTag."
    }
}

Invoke-Step "Ensuring ECS runtime resources"
Ensure-EcsCluster -ClusterName $clusterName
Ensure-LogGroup -LogGroupName $logGroupName
$executionRoleArn = Ensure-ExecutionRoleArn -RoleName $executionRoleName
$runtimeTaskRoleArn = if ($TaskRoleArn) { $TaskRoleArn } else { $executionRoleArn }
$taskDefArn = Register-TaskDefinition `
    -Family $taskFamily `
    -ImageUri "${repoUri}:$ImageTag" `
    -ExecutionRoleArn $executionRoleArn `
    -RuntimeTaskRoleArn $runtimeTaskRoleArn `
    -LogGroupName $logGroupName `
    -Port $ContainerPort `
    -TaskCpu $Cpu `
    -TaskMemory $Memory `
    -Region $AwsRegion

$networkConfig = $null
$taskArn = $null
if ($DeployService -or $SubnetIds.Count -gt 0 -or $SecurityGroupIds.Count -gt 0) {
    $networkConfig = To-NetworkConfigurationArg -Subnets $SubnetIds -SecurityGroups $SecurityGroupIds
}

if ($DeployService) {
    Ensure-Service -ClusterName $clusterName -ServiceName $serviceName -TaskDefinitionArn $taskDefArn -Count $DesiredCount -NetworkConfiguration $networkConfig
} elseif ($networkConfig) {
    $taskArn = Run-EphemeralTask -ClusterName $clusterName -TaskDefinitionArn $taskDefArn -NetworkConfiguration $networkConfig
}

$liveHealth = "skipped"
if ($Mode -eq "smoke") {
    $smokeUrl = [Environment]::GetEnvironmentVariable("PHASE0_SMOKE_URL")
    if (-not [string]::IsNullOrWhiteSpace($smokeUrl)) {
        Invoke-Step "Running live health check: $smokeUrl/health"
        try {
            $response = Invoke-WebRequest -Uri "$($smokeUrl.TrimEnd('/'))/health" -UseBasicParsing -TimeoutSec 15
            if ($response.Content -match "ok") {
                $liveHealth = "passed"
            } else {
                $liveHealth = "failed"
            }
        } catch {
            $liveHealth = "failed"
        }
    }
    & $PSCommandPath -Mode teardown -AwsRegion $AwsRegion -AwsProfile $AwsProfile -AppName $AppName -DeleteRepository:$DeleteRepository
}

$deployResult = @{
    mode               = $Mode
    aws_region         = $AwsRegion
    app_name           = $AppName
    ecr_repository_url = $repoUri
    ecs_cluster_name   = $clusterName
    ecs_service_name   = if ($DeployService) { $serviceName } else { $null }
    ecs_task_arn       = $taskArn
    ecs_task_def_arn   = $taskDefArn
    log_group_name     = $logGroupName
    deploy_service     = [bool]$DeployService
    live_health        = $liveHealth
}

$deployResult | ConvertTo-Json -Depth 4

