param(
    [switch]$Quiet = $true
)

$ErrorActionPreference = "Stop"

Write-Host "==> Syntax check (no pyc writes)"
python scripts/check_syntax.py backend tests scripts

Write-Host "==> Test suite"
if ($Quiet) {
    python scripts/run_tests.py tests/backend/test_backend_contracts.py tests/backend/test_orchestration_pipeline.py tests/e2e/test_phase0_roundtrip.py tests/e2e/test_aws_dev_deploy_smoke.py -q
}
else {
    python scripts/run_tests.py tests/backend/test_backend_contracts.py tests/backend/test_orchestration_pipeline.py tests/e2e/test_phase0_roundtrip.py tests/e2e/test_aws_dev_deploy_smoke.py
}

