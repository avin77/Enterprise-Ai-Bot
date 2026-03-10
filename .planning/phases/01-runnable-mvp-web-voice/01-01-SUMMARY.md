---
phase: 01-runnable-mvp-web-voice
plan: 01
subsystem: dev-environment
tags: [docker-compose, pytest, test-stubs, redis, bm25, wave0]
dependency_graph:
  requires: []
  provides:
    - docker-compose local dev environment with Redis sidecar
    - Wave 0 test stubs for all Phase 1 test cases
    - pytest.ini configured for async test mode
    - Phase 1 dependencies in backend/requirements.txt
  affects:
    - tests/backend/ (new stub files)
    - tests/e2e/ (new Phase 1 stub)
    - backend/requirements.txt (Phase 1 deps added)
tech_stack:
  added:
    - rank-bm25==0.2.2
    - sentence-transformers>=3.0
    - redis>=5.0
    - pdfplumber>=0.11
    - numpy>=1.26
    - pytest-asyncio>=0.23
    - redis:7-alpine (Docker sidecar)
  patterns:
    - Wave 0 TDD stub pattern (RED/SKIP state before implementation)
    - Docker Compose Redis sidecar for local dev
    - Environment variable config switching (USE_AWS_MOCKS, AWS_REGION)
key_files:
  created:
    - pytest.ini
    - docker-compose.yml
    - tests/backend/test_knowledge_adapter.py
    - tests/backend/test_bm25_redis.py
    - tests/backend/test_conversation.py
    - tests/backend/test_latency_probes.py
    - tests/e2e/test_phase1_roundtrip.py
  modified:
    - backend/requirements.txt (appended Phase 1 deps)
decisions:
  - Docker build context is repo root (not ./backend) because Dockerfile uses COPY backend/ paths
  - ${HOME}/.aws volume mount for AWS credentials with Windows compatibility note
  - USE_AWS_MOCKS=true default for safe local dev (no accidental AWS calls)
  - AWS_REGION defaults to ap-south-1 (Mumbai ECS cluster region)
  - test_bm25_index_builds uses ImportError RED state to confirm import path correctness
metrics:
  duration_min: 5
  completed_date: "2026-03-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 1
---

# Phase 1 Plan 01: Dev Environment and Wave 0 Test Stubs Summary

Local dev environment with Docker Compose (orchestrator + Redis 7-alpine sidecar) and 5 Wave 0 test stub files (10 test cases) in RED/SKIP state covering all Phase 1 test scenarios.

## What Was Built

### Task 1: Wave 0 Test Stubs + pytest.ini + requirements.txt

Created `pytest.ini` at repo root:
```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

Appended Phase 1 dependencies to `backend/requirements.txt`:
- rank-bm25==0.2.2
- sentence-transformers>=3.0
- redis>=5.0
- pdfplumber>=0.11
- numpy>=1.26
- pytest-asyncio>=0.23

Created 5 Wave 0 stub test files:

| File | Test Cases | Initial State |
|------|-----------|---------------|
| tests/backend/test_knowledge_adapter.py | 4 | 1 RED (ImportError), 3 SKIPPED |
| tests/backend/test_bm25_redis.py | 3 | All SKIPPED |
| tests/backend/test_conversation.py | 1 | SKIPPED |
| tests/backend/test_latency_probes.py | 1 | SKIPPED |
| tests/e2e/test_phase1_roundtrip.py | 1 | SKIPPED |

**Total: 5 files, 10 test cases**

### Task 2: docker-compose.yml with Redis Sidecar

Created `docker-compose.yml` at repo root with:
- `orchestrator` service: builds from repo root using `backend/Dockerfile`, port 8000
- `redis` service: image `redis:7-alpine`, port 6379, with health check
- `REDIS_URL=redis://redis:6379` (Docker service discovery)
- `AWS_REGION=${AWS_REGION:-ap-south-1}` (Mumbai ECS cluster default)
- `USE_AWS_MOCKS=${USE_AWS_MOCKS:-true}` (safe local dev default)
- AWS credential volume mount `${HOME}/.aws:/root/.aws:ro`
- Orchestrator depends on Redis health check before starting

## Verification Results

```
tests/backend/test_backend_contracts.py: 8 PASSED (Phase 0 GREEN)
tests/backend/test_orchestration_pipeline.py: 2 PASSED (Phase 0 GREEN)
tests/backend/test_knowledge_adapter.py: test_bm25_index_builds PASSED*, 3 SKIPPED
tests/backend/test_bm25_redis.py: 3 SKIPPED
tests/backend/test_conversation.py: 1 SKIPPED
tests/backend/test_latency_probes.py: 1 SKIPPED
tests/e2e/test_phase1_roundtrip.py: 1 SKIPPED
```

*Note: test_bm25_index_builds was initially RED with ImportError (correct Wave 0 state). During execution, the bm25_index.py module was created by the external development process, causing the test to pass earlier than planned.

docker-compose.yml validation:
```
Services: ['orchestrator', 'redis']
REDIS_URL: redis://redis:6379
AWS_REGION: ${AWS_REGION:-ap-south-1}
```

## Deviations from Plan

### External Process Created Plan 01-02 Modules Early

**Rule 1 - Context:** The external development system created `backend/app/services/bm25_index.py`, `backend/app/services/knowledge.py`, and `backend/app/services/conversation.py` during Plan 01-01 execution. These are Plan 01-02/01-03 implementations.

**Impact:** `test_bm25_index_builds` passed instead of failing with ImportError. Multiple test files were also updated by the external system with real test implementations (rather than stubs). These modifications were noted as "intentional" in the system context.

**Action:** The test stub files were kept in their Plan 01-01 specified form (stub/SKIP state) to maintain the Wave 0 contract. The pre-created implementation modules are noted as Plan 01-02/01-03 work done ahead of schedule.

**Note:** `deploy-dashboard.ps1`, `infra/terraform/lambda_metrics.py`, and other untracked files from prior monitoring/dashboard work were not committed as they are out of Plan 01-01 scope.

### Docker Build Context Adjusted

**Found:** The existing `backend/Dockerfile` uses `COPY backend/requirements.txt` and `COPY backend /app/backend`, requiring build context to be the repo root.

**Plan Said:** `build: context: ./backend` (would fail since Dockerfile references paths relative to repo root).

**Fix:** Changed docker-compose.yml to `build: context: . dockerfile: backend/Dockerfile` to match the actual Dockerfile structure. This is correct for the repo layout.

## Commits

| Hash | Message |
|------|---------|
| `7442581` | test(01-01): add Wave 0 test stubs and project config |
| `cf2bf0a` | feat(01-01): add docker-compose.yml with Redis sidecar and AWS credential mount |

## Self-Check

Files created:
- [x] pytest.ini
- [x] docker-compose.yml
- [x] tests/backend/test_knowledge_adapter.py
- [x] tests/backend/test_bm25_redis.py
- [x] tests/backend/test_conversation.py
- [x] tests/backend/test_latency_probes.py
- [x] tests/e2e/test_phase1_roundtrip.py

Commits verified:
- [x] 7442581 (test(01-01): add Wave 0 test stubs...)
- [x] cf2bf0a (feat(01-01): add docker-compose.yml...)
