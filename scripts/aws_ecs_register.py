#!/usr/bin/env python3
"""
Register ECS task definition for voice bot MVP.
Replaces PowerShell JSON parameter passing issues with direct Python boto3 calls.
"""

import json
import sys
import boto3
from typing import Optional

def register_task_definition(
    family: str,
    image_uri: str,
    execution_role_arn: str,
    task_role_arn: str,
    log_group: str,
    container_port: int,
    cpu: int,
    memory: int,
    region: str,
) -> Optional[str]:
    """Register ECS task definition and return ARN."""

    client = boto3.client("ecs", region_name=region)

    container_definitions = [
        {
            "name": "backend",
            "image": image_uri,
            "essential": True,
            "portMappings": [
                {
                    "containerPort": container_port,
                    "hostPort": container_port,
                    "protocol": "tcp",
                }
            ],
            "environment": [
                {"name": "AWS_REGION", "value": region},
                {"name": "USE_AWS_MOCKS", "value": "false"},
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": log_group,
                    "awslogs-region": region,
                    "awslogs-stream-prefix": "ecs",
                },
            },
        }
    ]

    response = client.register_task_definition(
        family=family,
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu=str(cpu),
        memory=str(memory),
        executionRoleArn=execution_role_arn,
        taskRoleArn=task_role_arn,
        containerDefinitions=container_definitions,
    )

    return response.get("taskDefinition", {}).get("taskDefinitionArn")


if __name__ == "__main__":
    family = sys.argv[1]
    image_uri = sys.argv[2]
    execution_role_arn = sys.argv[3]
    task_role_arn = sys.argv[4]
    log_group = sys.argv[5]
    container_port = int(sys.argv[6])
    cpu = int(sys.argv[7])
    memory = int(sys.argv[8])
    region = sys.argv[9]

    try:
        arn = register_task_definition(
            family=family,
            image_uri=image_uri,
            execution_role_arn=execution_role_arn,
            task_role_arn=task_role_arn,
            log_group=log_group,
            container_port=container_port,
            cpu=cpu,
            memory=memory,
            region=region,
        )
        if arn:
            print(arn)
            sys.exit(0)
        else:
            print("Error: No task definition ARN returned", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error registering task definition: {e}", file=sys.stderr)
        sys.exit(1)
