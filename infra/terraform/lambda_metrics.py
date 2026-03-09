"""
Lambda function to publish ECS metrics to CloudWatch
Triggered every 15 minutes by EventBridge
"""

import boto3
import os
from datetime import datetime, timedelta

ecs = boto3.client("ecs")
cloudwatch = boto3.client("cloudwatch")


def lambda_handler(event, context):
    """Main handler - publishes metrics to CloudWatch"""
    try:
        cluster_name = os.environ.get("CLUSTER_NAME")
        region = os.environ.get("AWS_REGION")

        print(f"[INFO] Publishing metrics for cluster: {cluster_name}")

        # Get ECS service info
        service_info = get_service_info(cluster_name)
        print(f"[INFO] Service: {service_info['service_name']}")
        print(f"[INFO] CPU: {service_info['cpu_units']}, Memory: {service_info['memory_mb']} MB")

        # Calculate costs
        costs = calculate_costs(service_info["cpu_units"], service_info["memory_mb"])
        print(f"[INFO] Costs - Hourly: ${costs['hourly']:.6f}, Monthly: ${costs['monthly']:.2f}")

        # Check for idle tasks
        idle_tasks = get_idle_tasks(cluster_name, hours_threshold=48)
        print(f"[INFO] Idle tasks found: {idle_tasks}")

        # Publish metrics
        publish_metrics(costs, idle_tasks)
        print("[SUCCESS] Metrics published to CloudWatch")

        return {
            "statusCode": 200,
            "body": f"Published metrics for {service_info['service_name']}",
        }

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}",
        }


def get_service_info(cluster_name):
    """Get ECS service configuration"""
    services = ecs.list_services(cluster=cluster_name)["serviceArns"]
    if not services:
        raise ValueError("No ECS services found")

    service_arn = services[0]
    service = ecs.describe_services(cluster=cluster_name, services=[service_arn])["services"][0]

    task_def_arn = service["taskDefinition"]
    task_def = ecs.describe_task_definition(taskDefinition=task_def_arn)["taskDefinition"]

    return {
        "cluster_name": cluster_name,
        "service_name": service["serviceName"],
        "cpu_units": int(task_def["cpu"]),
        "memory_mb": int(task_def["memory"]),
        "running_count": service["runningCount"],
        "desired_count": service["desiredCount"],
    }


def calculate_costs(cpu_units, memory_mb):
    """Calculate Fargate costs for ap-south-1"""
    cpu_vcpu = cpu_units / 1024
    memory_gb = memory_mb / 1024

    # Fargate rates (ap-south-1)
    cpu_rate = 0.0408  # USD per vCPU-hour
    memory_rate = 0.00450  # USD per GB-hour

    hourly_cost = (cpu_vcpu * cpu_rate) + (memory_gb * memory_rate)
    daily_cost = hourly_cost * 24
    monthly_cost = daily_cost * 30

    return {
        "hourly": round(hourly_cost, 6),
        "daily": round(daily_cost, 4),
        "monthly": round(monthly_cost, 2),
    }


def get_idle_tasks(cluster_name, hours_threshold=48):
    """Count tasks running longer than threshold"""
    now = datetime.utcnow()
    threshold_time = now - timedelta(hours=hours_threshold)

    tasks = ecs.list_tasks(cluster=cluster_name)["taskArns"]
    if not tasks:
        return 0

    task_details = ecs.describe_tasks(cluster=cluster_name, tasks=tasks)["tasks"]

    idle_count = 0
    for task in task_details:
        created_time = task["createdAt"].replace(tzinfo=None)
        if created_time < threshold_time:
            idle_count += 1

    return idle_count


def publish_metrics(costs, idle_tasks):
    """Publish custom metrics to CloudWatch"""
    timestamp = datetime.utcnow()

    metrics = [
        {
            "MetricName": "HourlyCost",
            "Value": costs["hourly"],
            "Unit": "None",
            "Timestamp": timestamp,
        },
        {
            "MetricName": "DailyCost",
            "Value": costs["daily"],
            "Unit": "None",
            "Timestamp": timestamp,
        },
        {
            "MetricName": "MonthlyCost",
            "Value": costs["monthly"],
            "Unit": "None",
            "Timestamp": timestamp,
        },
        {
            "MetricName": "IdleTasks",
            "Value": idle_tasks,
            "Unit": "Count",
            "Timestamp": timestamp,
        },
    ]

    cloudwatch.put_metric_data(
        Namespace="voicebot/operations",
        MetricData=metrics,
    )
