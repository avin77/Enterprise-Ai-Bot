import os
import subprocess
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


class AwsDevDeploySmokeTests(unittest.TestCase):
    def test_required_bootstrap_assets_exist(self) -> None:
        expected = [
            "backend/Dockerfile",
            "scripts/aws-bootstrap.ps1",
        ]
        for file_path in expected:
            self.assertTrue(Path(file_path).exists(), file_path)

    def test_bootstrap_script_contains_expected_commands(self) -> None:
        script = Path("scripts/aws-bootstrap.ps1").read_text(encoding="utf-8").lower()
        self.assertIn("docker build", script)
        self.assertIn("aws ecr get-login-password", script)
        self.assertIn("aws ecs register-task-definition", script)
        self.assertIn("aws ecs create-service", script)
        self.assertIn("aws ecs delete-service", script)
        self.assertIn("aws ecs run-task", script)

    def test_bootstrap_script_modes_and_no_terraform_dependency(self) -> None:
        script = Path("scripts/aws-bootstrap.ps1").read_text(encoding="utf-8").lower()
        self.assertIn('validateset("deploy", "teardown", "smoke")', script)
        self.assertNotIn("terraform -chdir=infra/terraform", script)
        self.assertNotIn("terraform version", script)

    def test_live_health_check_is_required(self) -> None:
        try:
            aws_check = subprocess.run(
                ["aws", "sts", "get-caller-identity", "--output", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            self.fail("Live AWS smoke is required: install AWS CLI and configure login/profile first.")
        self.assertEqual(
            aws_check.returncode,
            0,
            "Live AWS smoke is required: configure AWS CLI login/profile first.",
        )
        smoke_url = os.getenv("PHASE0_SMOKE_URL", "").strip()
        self.assertTrue(
            smoke_url,
            "Live AWS smoke is required: set PHASE0_SMOKE_URL to the deployed endpoint.",
        )
        req = Request(f"{smoke_url.rstrip('/')}/health", method="GET")
        with urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
        self.assertIn("ok", payload.lower())


def test_metrics_endpoint_structure():
    """GET /metrics returns JSON with asr, rag, llm, tts keys each having p50, p95, p99."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    for stage in ("asr", "rag", "llm", "tts"):
        assert stage in data, f"Missing stage '{stage}' in /metrics: {data}"
        for pct in ("p50", "p95", "p99"):
            assert pct in data[stage], f"Missing {pct} in /metrics.{stage}: {data[stage]}"


if __name__ == "__main__":
    unittest.main()
