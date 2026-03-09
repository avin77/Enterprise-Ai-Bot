# Lambda function to publish ECS metrics to CloudWatch
# Triggered every 15 minutes by EventBridge

data "archive_file" "metrics_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda_metrics.py"
  output_path = "${path.module}/lambda_metrics.zip"
}

resource "aws_iam_role" "lambda_metrics_role" {
  name = "${var.app_name}-lambda-metrics-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_metrics_policy" {
  name = "${var.app_name}-lambda-metrics-policy"
  role = aws_iam_role.lambda_metrics_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:ListServices",
          "ecs:ListClusters",
          "ecs:ListTasks",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "metrics_publisher" {
  filename            = data.archive_file.metrics_lambda.output_path
  function_name       = "${var.app_name}-metrics-publisher"
  role                = aws_iam_role.lambda_metrics_role.arn
  handler             = "lambda_metrics.lambda_handler"
  runtime             = "python3.11"
  timeout             = 60
  source_code_hash    = data.archive_file.metrics_lambda.output_base64sha256

  environment {
    variables = {
      CLUSTER_NAME = aws_ecs_cluster.main.name
      AWS_REGION   = var.aws_region
    }
  }
}

# EventBridge trigger - every 15 minutes
resource "aws_cloudwatch_event_rule" "metrics_schedule" {
  name                = "${var.app_name}-metrics-schedule"
  description         = "Trigger ECS metrics publishing every 15 minutes"
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "metrics_lambda" {
  rule      = aws_cloudwatch_event_rule.metrics_schedule.name
  target_id = "MetricsLambda"
  arn       = aws_lambda_function.metrics_publisher.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metrics_publisher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_schedule.arn
}

output "lambda_function_name" {
  description = "Lambda function name for metrics publishing"
  value       = aws_lambda_function.metrics_publisher.function_name
}

output "metrics_schedule_rule" {
  description = "EventBridge rule for metrics schedule"
  value       = aws_cloudwatch_event_rule.metrics_schedule.name
}
