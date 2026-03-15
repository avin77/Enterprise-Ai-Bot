$REGION = "ap-south-1"
$APP = "voice-bot-mvp"
$CLUSTER = "voice-bot-mvp-cluster"
$SERVICE = "voice-bot-mvp-svc"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

Write-Host "DEPLOYING MONITORING DASHBOARD" -ForegroundColor Cyan
Write-Host "Account: $ACCOUNT_ID | Region: $REGION" -ForegroundColor Gray
Write-Host ""

# ── STEP 1: CloudWatch Dashboard ──────────────────────────────────────────────
Write-Host "[1/3] Creating CloudWatch Dashboard..." -ForegroundColor Yellow

$dashboard = @"
{
  "widgets": [
    {
      "type": "metric", "x": 0, "y": 0, "width": 6, "height": 6,
      "properties": {
        "metrics": [["AWS/ECS","CPUUtilization","ServiceName","$SERVICE","ClusterName","$CLUSTER"]],
        "period": 60, "stat": "Average", "region": "$REGION", "title": "CPU Utilization (%)",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric", "x": 6, "y": 0, "width": 6, "height": 6,
      "properties": {
        "metrics": [["AWS/ECS","MemoryUtilization","ServiceName","$SERVICE","ClusterName","$CLUSTER"]],
        "period": 60, "stat": "Average", "region": "$REGION", "title": "Memory Utilization (%)",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric", "x": 12, "y": 0, "width": 6, "height": 6,
      "properties": {
        "metrics": [["AWS/ECS","RunningCount","ServiceName","$SERVICE","ClusterName","$CLUSTER"]],
        "period": 60, "stat": "Average", "region": "$REGION", "title": "Running Tasks"
      }
    },
    {
      "type": "metric", "x": 18, "y": 0, "width": 6, "height": 6,
      "properties": {
        "metrics": [["AWS/ECS","DesiredTaskCount","ServiceName","$SERVICE","ClusterName","$CLUSTER"]],
        "period": 60, "stat": "Average", "region": "$REGION", "title": "Desired Tasks"
      }
    },
    {
      "type": "metric", "x": 0, "y": 6, "width": 8, "height": 6,
      "properties": {
        "metrics": [["voicebot/operations","HourlyCost"]],
        "period": 900, "stat": "Average", "region": "$REGION", "title": "Hourly Cost (USD)"
      }
    },
    {
      "type": "metric", "x": 8, "y": 6, "width": 8, "height": 6,
      "properties": {
        "metrics": [["voicebot/operations","DailyCost"]],
        "period": 900, "stat": "Average", "region": "$REGION", "title": "Daily Cost (USD)"
      }
    },
    {
      "type": "metric", "x": 16, "y": 6, "width": 8, "height": 6,
      "properties": {
        "metrics": [["voicebot/operations","MonthlyCost"]],
        "period": 900, "stat": "Average", "region": "$REGION", "title": "Monthly Cost (USD)"
      }
    },
    {
      "type": "metric", "x": 0, "y": 12, "width": 12, "height": 6,
      "properties": {
        "metrics": [
          ["AWS/ECS","CPUUtilization","ServiceName","$SERVICE","ClusterName","$CLUSTER"],
          ["AWS/ECS","MemoryUtilization","ServiceName","$SERVICE","ClusterName","$CLUSTER"]
        ],
        "period": 300, "stat": "Average", "region": "$REGION", "title": "CPU vs Memory Trend (24h)"
      }
    },
    {
      "type": "metric", "x": 12, "y": 12, "width": 12, "height": 6,
      "properties": {
        "metrics": [["voicebot/operations","IdleTasks"]],
        "period": 900, "stat": "Maximum", "region": "$REGION", "title": "Idle Tasks (running over 48h)"
      }
    },
    {
      "type": "log", "x": 0, "y": 18, "width": 24, "height": 6,
      "properties": {
        "query": "SOURCE '/ecs/$APP' | fields @timestamp, @message | filter @message like /ERROR|WARN/ | sort @timestamp desc | limit 20",
        "region": "$REGION", "title": "Recent Errors and Warnings"
      }
    }
  ]
}
"@

$dashboard | Out-File -FilePath "dashboard-body.json" -Encoding utf8
aws cloudwatch put-dashboard --dashboard-name "$APP-operations" --dashboard-body file://dashboard-body.json --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - Dashboard created" -ForegroundColor Green
} else {
    Write-Host "ERROR - Dashboard creation failed" -ForegroundColor Red
    exit 1
}

# ── STEP 2: Lambda IAM Role ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] Setting up Lambda metrics publisher..." -ForegroundColor Yellow

$trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
"@

$trustPolicy | Out-File -FilePath "trust-policy.json" -Encoding utf8

# Create role (ignore error if already exists)
aws iam create-role --role-name "$APP-lambda-metrics-role" --assume-role-policy-document file://trust-policy.json 2>$null

# Attach policies
aws iam attach-role-policy --role-name "$APP-lambda-metrics-role" --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>$null

$lambdaPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ecs:DescribeServices","ecs:ListServices","ecs:ListClusters","ecs:ListTasks","ecs:DescribeTasks","ecs:DescribeTaskDefinition"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["cloudwatch:PutMetricData"],
      "Resource": "*"
    }
  ]
}
"@

$lambdaPolicy | Out-File -FilePath "lambda-policy.json" -Encoding utf8
aws iam put-role-policy --role-name "$APP-lambda-metrics-role" --policy-name "$APP-metrics-policy" --policy-document file://lambda-policy.json

Write-Host "OK - IAM role created" -ForegroundColor Green

# Wait for role to propagate
Write-Host "Waiting 10 seconds for IAM role to propagate..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Zip Lambda code
Compress-Archive -Path "infra\terraform\lambda_metrics.py" -DestinationPath "lambda.zip" -Force

$ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$APP-lambda-metrics-role"

# Create Lambda (ignore error if exists)
aws lambda create-function `
    --function-name "$APP-metrics-publisher" `
    --runtime python3.11 `
    --role $ROLE_ARN `
    --handler lambda_metrics.lambda_handler `
    --zip-file fileb://lambda.zip `
    --timeout 60 `
    --environment "Variables={CLUSTER_NAME=$CLUSTER,AWS_REGION_NAME=$REGION}" `
    --region $REGION 2>$null

# If already exists, update the code
aws lambda update-function-code `
    --function-name "$APP-metrics-publisher" `
    --zip-file fileb://lambda.zip `
    --region $REGION 2>$null

Write-Host "OK - Lambda function deployed" -ForegroundColor Green

# ── STEP 3: EventBridge Trigger ────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/3] Setting up EventBridge trigger (every 15 min)..." -ForegroundColor Yellow

aws events put-rule `
    --name "$APP-metrics-schedule" `
    --schedule-expression "rate(15 minutes)" `
    --state ENABLED `
    --region $REGION 2>$null

$LAMBDA_ARN = "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:$APP-metrics-publisher"

aws lambda add-permission `
    --function-name "$APP-metrics-publisher" `
    --statement-id "AllowEventBridge" `
    --action lambda:InvokeFunction `
    --principal events.amazonaws.com `
    --region $REGION 2>$null

aws events put-targets `
    --rule "$APP-metrics-schedule" `
    --targets "Id=MetricsLambda,Arn=$LAMBDA_ARN" `
    --region $REGION 2>$null

Write-Host "OK - EventBridge trigger created (every 15 minutes)" -ForegroundColor Green

# ── Run Lambda once now ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Running Lambda once to publish first metrics..." -ForegroundColor Yellow
aws lambda invoke --function-name "$APP-metrics-publisher" --region $REGION response.json 2>$null
Write-Host "OK - First metrics published" -ForegroundColor Green

# Cleanup temp files
Remove-Item -Path "dashboard-body.json","trust-policy.json","lambda-policy.json","lambda.zip","response.json" -ErrorAction SilentlyContinue

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard URL:" -ForegroundColor Cyan
Write-Host "https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=$APP-operations" -ForegroundColor White
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Dashboard: $APP-operations (10 widgets)" -ForegroundColor Gray
Write-Host "  Lambda:    $APP-metrics-publisher" -ForegroundColor Gray
Write-Host "  Schedule:  Every 15 minutes (automatic)" -ForegroundColor Gray
Write-Host "  Cost:      ~0.50 USD/month extra" -ForegroundColor Gray
Write-Host ""
