# CloudWatch Dashboards and Alarms for ECS Resource Monitoring

resource "aws_cloudwatch_dashboard" "ecs_resources" {
  dashboard_name = "${var.app_name}-resources"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "CPU & Memory Utilization (%)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
        width  = 12
        height = 6
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "DesiredTaskCount", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name],
            [".", "RunningCount", ".", ".", ".", "."]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Task Count"
        }
        width  = 12
        height = 6
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count               = var.deploy_service ? 1 : 0
  alarm_name          = "${var.app_name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Alert when CPU exceeds 80%"
  dimensions = {
    ServiceName = aws_ecs_service.backend[0].name
    ClusterName = aws_ecs_cluster.main.name
  }
}

resource "aws_cloudwatch_metric_alarm" "memory_high" {
  count               = var.deploy_service ? 1 : 0
  alarm_name          = "${var.app_name}-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "Alert when memory exceeds 85%"
  dimensions = {
    ServiceName = aws_ecs_service.backend[0].name
    ClusterName = aws_ecs_cluster.main.name
  }
}

# Custom metrics for task-level monitoring
resource "aws_log_group" "metrics" {
  name              = "/ecs/${var.app_name}/metrics"
  retention_in_days = 30
}

output "cloudwatch_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.ecs_resources.dashboard_name}"
}

output "cpu_alarm_name" {
  value = try(aws_cloudwatch_metric_alarm.cpu_high[0].alarm_name, "N/A")
}

output "memory_alarm_name" {
  value = try(aws_cloudwatch_metric_alarm.memory_high[0].alarm_name, "N/A")
}
