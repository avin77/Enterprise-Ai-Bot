# tests/backend/test_infra_config.py
"""Tests for ECS task definition, IAM policy, and FAQ loader configuration."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_ecs_task_definition_memory_cpu():
    """ECS task definition specifies memory=1024, cpu=512."""
    td = json.loads(Path("infra/ecs_task_definition.json").read_text())
    assert td["memory"] == "1024", f"Expected 1024MB, got {td['memory']}"
    assert td["cpu"] == "512", f"Expected 512 CPU, got {td['cpu']}"


def test_ecs_task_definition_containers():
    """ECS task definition has two containers: orchestrator and redis sidecar."""
    td = json.loads(Path("infra/ecs_task_definition.json").read_text())
    containers = td["containerDefinitions"]
    assert len(containers) == 2, f"Expected 2 containers, got {len(containers)}"
    names = {c["name"] for c in containers}
    assert "orchestrator" in names, f"Missing orchestrator container: {names}"
    assert "redis" in names, f"Missing redis sidecar container: {names}"


def test_ecs_task_definition_region_ap_south1():
    """ECS task definition log config uses ap-south-1 region."""
    td = json.loads(Path("infra/ecs_task_definition.json").read_text())
    orchestrator = next(c for c in td["containerDefinitions"] if c["name"] == "orchestrator")
    log_region = orchestrator["logConfiguration"]["options"]["awslogs-region"]
    assert log_region == "ap-south-1", f"Expected ap-south-1 region, got {log_region}"


def test_ecs_task_definition_task_role():
    """ECS task definition references voicebot-task-role."""
    td = json.loads(Path("infra/ecs_task_definition.json").read_text())
    assert "voicebot-task-role" in td.get("taskRoleArn", ""), \
        f"taskRoleArn missing voicebot-task-role: {td.get('taskRoleArn')}"


def test_iam_policy_has_required_permissions():
    """IAM policy includes all 9 required permissions from ROADMAP.md."""
    policy = json.loads(Path("infra/iam_task_role_policy.json").read_text())
    actions = [a for stmt in policy["Statement"] for a in stmt["Action"]]
    required = [
        "dynamodb:Scan",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:UpdateItem",
        "s3:GetObject",
        "s3:ListBucket",
        "cloudwatch:PutMetricData",
    ]
    missing = [r for r in required if r not in actions]
    assert not missing, f"Missing required IAM actions: {missing}"


def test_iam_policy_has_bedrock_permissions():
    """IAM policy includes Bedrock inference permissions."""
    policy = json.loads(Path("infra/iam_task_role_policy.json").read_text())
    actions = [a for stmt in policy["Statement"] for a in stmt["Action"]]
    assert "bedrock:InvokeModel" in actions, "Missing bedrock:InvokeModel"
    assert "bedrock:InvokeModelWithResponseStream" in actions, "Missing bedrock:InvokeModelWithResponseStream"


def test_load_faqs_dry_run(tmp_path):
    """load_faqs_to_dynamo dry-run returns correct count without calling DynamoDB."""
    # Create a minimal sample_faqs.json for testing
    faqs = [
        {"department": "tax", "chunk_id": "faq:0", "answer": "Tax answer 1"},
        {"department": "voter", "chunk_id": "faq:1", "answer": "Voter answer 1"},
        {"department": "general", "chunk_id": "faq:2", "answer": "General answer 1"},
    ]
    faq_file = tmp_path / "sample_faqs.json"
    faq_file.write_text(json.dumps(faqs))

    from knowledge.scripts.load_faqs import load_faqs_to_dynamo
    # In dry_run mode, no DynamoDB calls are made — no AWS credentials needed
    count = load_faqs_to_dynamo(
        table_name="voicebot-faq-knowledge",
        region="ap-south-1",
        faq_path=str(faq_file),
        dry_run=True,
    )
    assert count == 3, f"Expected 3 items counted, got {count}"
