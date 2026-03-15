#!/usr/bin/env python3
"""
Publish custom ECS metrics to CloudWatch for PM monitoring dashboard.
Runs every 15 minutes to track:
- Cost (hourly, daily, monthly)
- Idle tasks (running > 2 days)
- Resource efficiency
"""

import boto3
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Fix encoding for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

cloudwatch = boto3.client("cloudwatch", region_name="ap-south-1")
ecs = boto3.client("ecs", region_name="ap-south-1")


def get_service_info() -> dict:
    """Get current ECS service configuration."""
    clusters = ecs.list_clusters()["clusterArns"]
    if not clusters:
        raise ValueError("No ECS clusters found")

    cluster_arn = clusters[0]
    cluster_name = cluster_arn.split("/")[-1]

    services = ecs.list_services(cluster=cluster_arn)["serviceArns"]
    if not services:
        raise ValueError("No ECS services found")

    service_arn = services[0]
    service = ecs.describe_services(cluster=cluster_arn, services=[service_arn])["services"][0]

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


def calculate_costs(cpu_units: int, memory_mb: int) -> dict:
    """Calculate Fargate costs."""
    # AWS Fargate pricing (ap-south-1)
    cpu_vcpu = cpu_units / 1024
    memory_gb = memory_mb / 1024

    # Fargate rates (ap-south-1 pricing)
    cpu_rate = 0.0408  # USD per vCPU-hour
    memory_rate = 0.00450  # USD per GB-hour

    hourly_cost = (cpu_vcpu * cpu_rate) + (memory_gb * memory_rate)
    daily_cost = hourly_cost * 24
    monthly_cost = daily_cost * 30

    return {
        "hourly": round(hourly_cost, 6),
        "daily": round(daily_cost, 4),
        "monthly": round(monthly_cost, 2),
        "cpu_vcpu": cpu_vcpu,
        "memory_gb": memory_gb,
    }


def get_idle_tasks(cluster_name: str, hours_threshold: int = 48) -> int:
    """Count tasks running longer than threshold."""
    now = datetime.utcnow()
    threshold_time = now - timedelta(hours=hours_threshold)

    tasks = ecs.list_tasks(cluster=cluster_name)["taskArns"]
    if not tasks:
        return 0

    task_details = ecs.describe_tasks(cluster=cluster_name, tasks=tasks)["tasks"]

    idle_count = 0
    for task in task_details:
        # Convert created time to UTC-aware datetime
        created_time = task["createdAt"].replace(tzinfo=None)

        if created_time < threshold_time:
            idle_count += 1
            print(f"  [WARN] Idle task found: {task['taskArn'].split('/')[-1]} (created {created_time})")

    return idle_count


def calculate_efficiency(
    cpu_utilization: float, memory_utilization: float
) -> dict:
    """Calculate resource efficiency score."""
    # Score: How close to 100% without wasting. Optimal is 50-70%
    cpu_score = 100 - abs(50 - cpu_utilization)  # 0 at 0% or 100%, 100 at 50%
    memory_score = 100 - abs(50 - memory_utilization)

    overall_score = (cpu_score + memory_score) / 2

    return {
        "overall": round(max(0, overall_score), 1),
        "cpu": round(max(0, cpu_score), 1),
        "memory": round(max(0, memory_score), 1),
    }


def publish_metrics(service_info: dict, costs: dict, idle_tasks: int):
    """Publish custom metrics to CloudWatch."""
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

    # Publish metrics
    cloudwatch.put_metric_data(
        Namespace="voicebot/operations",
        MetricData=metrics,
    )

    print(f"[OK] Published metrics at {timestamp.isoformat()}")
    for metric in metrics:
        print(f"   {metric['MetricName']}: {metric['Value']}")


def main():
    """Main execution."""
    try:
        print("\n" + "=" * 60)
        print("Publishing Custom CloudWatch Metrics")
        print("=" * 60 + "\n")

        # Get ECS info
        print("[INFO] Fetching ECS configuration...")
        service_info = get_service_info()
        print(f"   Cluster: {service_info['cluster_name']}")
        print(f"   Service: {service_info['service_name']}")
        print(f"   CPU: {service_info['cpu_units']} units")
        print(f"   Memory: {service_info['memory_mb']} MB")
        print(f"   Running tasks: {service_info['running_count']}")

        # Calculate costs
        print("\n[INFO] Calculating costs...")
        costs = calculate_costs(service_info["cpu_units"], service_info["memory_mb"])
        print(f"   Hourly: ${costs['hourly']}")
        print(f"   Daily: ${costs['daily']}")
        print(f"   Monthly: ${costs['monthly']}")

        # Check for idle tasks
        print("\n[INFO] Checking for idle tasks (running > 48 hours)...")
        idle_tasks = get_idle_tasks(service_info["cluster_name"], hours_threshold=48)
        print(f"   Idle tasks found: {idle_tasks}")

        # Publish to CloudWatch
        print("\n[INFO] Publishing to CloudWatch...")
        publish_metrics(service_info, costs, idle_tasks)

        print("\n" + "=" * 60)
        print("[SUCCESS] Complete! Metrics available in CloudWatch")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
