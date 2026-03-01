import os
import subprocess
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


class AwsDevDeploySmokeTests(unittest.TestCase):
    def test_required_bootstrap_assets_exist(self) -> None:
        expected = [
            "backend/Dockerfile",
            "infra/terraform/main.tf",
            "infra/terraform/variables.tf",
            "infra/terraform/outputs.tf",
            "scripts/aws-bootstrap.ps1",
        ]
        for file_path in expected:
            self.assertTrue(Path(file_path).exists(), file_path)

    def test_terraform_defines_ecr_and_ecs_resources(self) -> None:
        content = Path("infra/terraform/main.tf").read_text(encoding="utf-8")
        self.assertIn('resource "aws_ecr_repository" "backend"', content)
        self.assertIn('resource "aws_ecs_cluster" "main"', content)
        self.assertIn('resource "aws_ecs_task_definition" "backend"', content)
        self.assertIn('default     = "us-east-1"', Path("infra/terraform/variables.tf").read_text(encoding="utf-8"))

    def test_bootstrap_script_contains_expected_commands(self) -> None:
        script = Path("scripts/aws-bootstrap.ps1").read_text(encoding="utf-8").lower()
        self.assertIn("docker build", script)
        self.assertIn("terraform -chdir=infra/terraform apply", script)
        self.assertIn("aws ecr get-login-password", script)

    def test_terraform_validate_if_available(self) -> None:
        terraform = "terraform"
        try:
            check = subprocess.run(
                [terraform, "version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            self.skipTest("terraform not installed in local environment")
            return
        if check.returncode != 0:
            self.skipTest("terraform not installed in local environment")
        validate = subprocess.run(
            [terraform, "-chdir=infra/terraform", "validate"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_live_health_check_when_url_provided(self) -> None:
        smoke_url = os.getenv("PHASE0_SMOKE_URL", "").strip()
        if not smoke_url:
            self.skipTest("set PHASE0_SMOKE_URL to run live AWS health smoke")
        req = Request(f"{smoke_url.rstrip('/')}/health", method="GET")
        with urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
        self.assertIn("ok", payload.lower())


if __name__ == "__main__":
    unittest.main()
