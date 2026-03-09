# CloudWatch Dashboard - Senior PM Monitoring
# Fully automated, no manual setup required

resource "aws_cloudwatch_dashboard" "pm_operations" {
  count          = var.deploy_service ? 1 : 0
  dashboard_name = "${var.app_name}-operations"

  dashboard_body = jsonencode({
    widgets = [
      # ROW 1: Resource Health (CPU, Memory, Tasks)
      {
        type = "metric"
        x    = 0
        y    = 0
        width = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "CPU Utilization (%)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        x    = 6
        y    = 0
        width = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "MemoryUtilization", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Memory Utilization (%)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        x    = 12
        y    = 0
        width = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "RunningCount", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Running Tasks"
        }
      },
      {
        type = "metric"
        x    = 18
        y    = 0
        width = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "DesiredTaskCount", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Desired Tasks"
        }
      },

      # ROW 2: Cost Metrics
      {
        type = "metric"
        x    = 0
        y    = 6
        width = 6
        height = 6
        properties = {
          metrics = [
            ["voicebot/operations", "HourlyCost"]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Hourly Cost (USD)"
        }
      },
      {
        type = "metric"
        x    = 6
        y    = 6
        width = 6
        height = 6
        properties = {
          metrics = [
            ["voicebot/operations", "DailyCost"]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Daily Cost (USD)"
        }
      },
      {
        type = "metric"
        x    = 12
        y    = 6
        width = 6
        height = 6
        properties = {
          metrics = [
            ["voicebot/operations", "MonthlyCost"]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Monthly Cost (USD)"
        }
      },
      {
        type = "metric"
        x    = 18
        y    = 6
        width = 6
        height = 6
        properties = {
          metrics = [
            ["voicebot/operations", "IdleTasks"]
          ]
          period = 60
          stat   = "Maximum"
          region = var.aws_region
          title  = "Idle Tasks (>48h)"
        }
      },

      # ROW 3: Cost Trend
      {
        type = "metric"
        x    = 0
        y    = 12
        width = 12
        height = 6
        properties = {
          metrics = [
            ["voicebot/operations", "DailyCost"],
            ["...", "MonthlyCost"]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Cost Trend (24h)"
        }
      },

      # ROW 3: Task Health
      {
        type = "metric"
        x    = 12
        y    = 12
        width = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "RunningCount", "ServiceName", aws_ecs_service.backend[0].name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Task Count History"
        }
      },

      # ROW 4: Logs Insight
      {
        type = "log"
        x    = 0
        y    = 18
        width = 24
        height = 6
        properties = {
          query   = "SOURCE '/ecs/${var.app_name}' | fields @timestamp, @message | filter @message like /ERROR|WARN/ | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Errors & Warnings"
        }
      }
    ]
  })
}

output "dashboard_url" {
  description = "CloudWatch Dashboard URL"
  value       = try("https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.pm_operations[0].dashboard_name}", "")
}
