#!/usr/bin/env python3
"""
ECS Resource Utilization Monitor & Reporter
Pulls CloudWatch metrics and generates resource optimization recommendations.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Any

import boto3

cloudwatch = boto3.client("cloudwatch")
ecs = boto3.client("ecs")


def get_cluster_and_service(app_name: str) -> tuple[str, str]:
    """Get cluster and service names from ECS."""
    clusters = ecs.list_clusters()["clusterArns"]
    if not clusters:
        raise ValueError("No ECS clusters found")

    cluster_arn = clusters[0]
    cluster_name = cluster_arn.split("/")[-1]

    services = ecs.list_services(cluster=cluster_arn)["serviceArns"]
    if not services:
        raise ValueError("No ECS services found")

    service_arn = services[0]
    service_name = service_arn.split("/")[-1]

    return cluster_name, service_name


def get_metrics(
    service_name: str, cluster_name: str, hours: int = 24
) -> dict[str, Any]:
    """Fetch CPU and memory metrics from CloudWatch."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    metrics = {}

    # Get CPU Utilization
    cpu_response = cloudwatch.get_metric_statistics(
        Namespace="AWS/ECS",
        MetricName="CPUUtilization",
        Dimensions=[
            {"Name": "ServiceName", "Value": service_name},
            {"Name": "ClusterName", "Value": cluster_name},
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,  # 5-min intervals
        Statistics=["Average", "Maximum"],
    )

    # Get Memory Utilization
    memory_response = cloudwatch.get_metric_statistics(
        Namespace="AWS/ECS",
        MetricName="MemoryUtilization",
        Dimensions=[
            {"Name": "ServiceName", "Value": service_name},
            {"Name": "ClusterName", "Value": cluster_name},
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=["Average", "Maximum"],
    )

    if cpu_response["Datapoints"]:
        cpu_avgs = [d["Average"] for d in cpu_response["Datapoints"]]
        cpu_maxes = [d["Maximum"] for d in cpu_response["Datapoints"]]
        metrics["cpu"] = {
            "avg": sum(cpu_avgs) / len(cpu_avgs),
            "max": max(cpu_maxes),
            "min": min(cpu_avgs),
            "samples": len(cpu_avgs),
        }
    else:
        metrics["cpu"] = {"avg": None, "max": None, "min": None, "samples": 0}

    if memory_response["Datapoints"]:
        mem_avgs = [d["Average"] for d in memory_response["Datapoints"]]
        mem_maxes = [d["Maximum"] for d in memory_response["Datapoints"]]
        metrics["memory"] = {
            "avg": sum(mem_avgs) / len(mem_avgs),
            "max": max(mem_maxes),
            "min": min(mem_avgs),
            "samples": len(mem_avgs),
        }
    else:
        metrics["memory"] = {"avg": None, "max": None, "min": None, "samples": 0}

    return metrics


def get_task_definition(service_name: str, cluster_name: str) -> dict[str, Any]:
    """Get current task definition."""
    service = ecs.describe_services(cluster=cluster_name, services=[service_name])[
        "services"
    ][0]
    task_def_arn = service["taskDefinition"]
    task_def = ecs.describe_task_definition(taskDefinition=task_def_arn)[
        "taskDefinition"
    ]

    return {
        "cpu": int(task_def["cpu"]),
        "memory": int(task_def["memory"]),
        "desired_count": service["desiredCount"],
        "running_count": service["runningCount"],
    }


def recommend_resources(
    cpu_util: dict[str, Any], mem_util: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    """Generate resource optimization recommendations."""
    recommendations = {"safe": False, "suggested_cpu": current["cpu"], "suggested_memory": current["memory"], "reasoning": []}

    cpu_max = cpu_util.get("max", 0)
    mem_max = mem_util.get("max", 0)
    cpu_avg = cpu_util.get("avg", 0)
    mem_avg = mem_util.get("avg", 0)

    # Check if current resources are sufficient
    if cpu_max is not None and mem_max is not None:
        if cpu_max > 90 or mem_max > 90:
            recommendations["reasoning"].append(
                f"⚠️  MAX utilization: CPU {cpu_max:.1f}%, Memory {mem_max:.1f}% - SCALING UP NEEDED"
            )
            recommendations["safe"] = False

            # Suggest scaling
            if cpu_max > 90:
                current_cpu = current["cpu"]
                recommendations["suggested_cpu"] = int(current_cpu * 2)
                recommendations["reasoning"].append(
                    f"  → CPU: {current_cpu} → {recommendations['suggested_cpu']} vCPU units"
                )

            if mem_max > 90:
                current_mem = current["memory"]
                recommendations["suggested_memory"] = int(current_mem * 1.5)
                recommendations["reasoning"].append(
                    f"  → Memory: {current_mem} → {recommendations['suggested_memory']} MB"
                )
        else:
            recommendations["safe"] = True
            recommendations["reasoning"].append(
                f"✓ Current resources sufficient. Max utilization: CPU {cpu_max:.1f}%, Memory {mem_max:.1f}%"
            )

            # Check if oversized (only 10% utilization)
            if cpu_avg is not None and cpu_avg < 10 and cpu_max < 30:
                recommendations["reasoning"].append(
                    f"⚡ Opportunity to OPTIMIZE: Average CPU only {cpu_avg:.1f}% (max {cpu_max:.1f}%)"
                )

                # Suggest downsizing
                min_cpu = 128
                if current["cpu"] > min_cpu:
                    recommendations["suggested_cpu"] = max(min_cpu, int(current["cpu"] / 2))
                    recommendations["reasoning"].append(
                        f"  → Could reduce CPU: {current['cpu']} → {recommendations['suggested_cpu']} units (SAVE ~50%)"
                    )

            if mem_avg is not None and mem_avg < 20 and mem_max < 50:
                recommendations["reasoning"].append(
                    f"⚡ Opportunity to OPTIMIZE: Average memory only {mem_avg:.1f}% (max {mem_max:.1f}%)"
                )

                min_mem = 256
                if current["memory"] > min_mem:
                    recommendations["suggested_memory"] = max(min_mem, int(current["memory"] / 2))
                    recommendations["reasoning"].append(
                        f"  → Could reduce memory: {current['memory']} → {recommendations['suggested_memory']} MB (SAVE ~50%)"
                    )

    return recommendations


def generate_report(app_name: str, hours: int = 24):
    """Generate and print resource utilization report."""
    print("\n" + "=" * 70)
    print(f"ECS RESOURCE UTILIZATION REPORT - {app_name.upper()}")
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Analysis Period: Last {hours} hours")
    print("=" * 70 + "\n")

    try:
        # Get cluster and service info
        cluster_name, service_name = get_cluster_and_service(app_name)
        print(f"Cluster: {cluster_name}")
        print(f"Service: {service_name}\n")

        # Get current task definition
        current = get_task_definition(service_name, cluster_name)
        print("CURRENT CONFIGURATION:")
        print(f"  CPU:             {current['cpu']} units (0.{current['cpu']//256} vCPU)")
        print(f"  Memory:          {current['memory']} MB")
        print(f"  Desired Tasks:   {current['desired_count']}")
        print(f"  Running Tasks:   {current['running_count']}")
        print()

        # Fetch metrics
        print("Fetching CloudWatch metrics...")
        metrics = get_metrics(service_name, cluster_name, hours)

        print("\nCPU UTILIZATION:")
        if metrics["cpu"]["samples"] > 0:
            print(f"  Average:  {metrics['cpu']['avg']:.1f}%")
            print(f"  Maximum:  {metrics['cpu']['max']:.1f}%")
            print(f"  Minimum:  {metrics['cpu']['min']:.1f}%")
            print(f"  Samples:  {metrics['cpu']['samples']}")
        else:
            print("  ⚠️  No data available (service may be new)")

        print("\nMEMORY UTILIZATION:")
        if metrics["memory"]["samples"] > 0:
            print(f"  Average:  {metrics['memory']['avg']:.1f}%")
            print(f"  Maximum:  {metrics['memory']['max']:.1f}%")
            print(f"  Minimum:  {metrics['memory']['min']:.1f}%")
            print(f"  Samples:  {metrics['memory']['samples']}")
        else:
            print("  ⚠️  No data available (service may be new)")

        # Generate recommendations
        recommendations = recommend_resources(metrics["cpu"], metrics["memory"], current)

        print("\nRECOMMENDATIONS:")
        for note in recommendations["reasoning"]:
            print(f"  {note}")

        if not recommendations["safe"]:
            print(f"\n  📊 SUGGESTED CONFIGURATION:")
            print(f"     CPU:    {current['cpu']} → {recommendations['suggested_cpu']} units")
            print(f"     Memory: {current['memory']} → {recommendations['suggested_memory']} MB")
            print(f"\n  Apply with: terraform apply -var='cpu={recommendations['suggested_cpu']}' -var='memory={recommendations['suggested_memory']}'")

        print("\n" + "=" * 70)

        # Return as JSON for automation
        return {
            "cluster": cluster_name,
            "service": service_name,
            "current": current,
            "metrics": metrics,
            "recommendations": recommendations,
        }

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Ensure AWS credentials are configured and the service is deployed.")
        sys.exit(1)


if __name__ == "__main__":
    app_name = sys.argv[1] if len(sys.argv) > 1 else "voice-bot-mvp"
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24

    report_data = generate_report(app_name, hours)

    # Save JSON report
    report_file = f"resource-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2, default=str)
    print(f"\nJSON report saved to: {report_file}")
