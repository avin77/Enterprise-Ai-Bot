# 📄 Phase 0: Learning MVP Bootstrap - Master Spec
**Status:** Completed (2026-03-01) | **Owner:** Product Management | **Technical Lead:** Engineering

---

## 1. Executive Summary
### Problem Statement
Developers and stakeholders lacked a stable, authenticated "sandbox" to test the voice-to-voice loop without exposing cloud credentials in the frontend or managing complex AWS infrastructure.
### Proposed Solution
A "Learning MVP" consisting of a FastAPI backend gateway, swappable AI adapters (Mock/AWS), and a basic web client that communicates strictly via the backend endpoints.
### Business Impact
- **Security:** Zero AWS credentials in the frontend; centralized IAM-based access in the backend.
- **Velocity:** Established a local "Mock Mode" that allows developers to test the voice loop without cloud dependency.
- **Foundation:** Created a pluggable adapter architecture that prevents vendor lock-in for STT/LLM/TTS providers.

---

## 2. Problem Definition & Market Opportunity
### 2.1 Customer Problem
As a developer, I want to iterate on voice-response logic without waiting for production-grade AWS setups. I need a way to simulate voice roundtrips locally while ensuring the code is "Cloud Ready."
### 2.2 Strategic Value
Establishing the **Adapter Pattern** early ensures we can swap AI models (e.g., from Bedrock to OpenAI) in later phases with zero changes to the core application logic or API contracts.

---

## 3. Solution Overview
### 3.1 Proposed Architecture
A three-tier streaming system:
1. **Frontend:** Captures mic input; sends binary chunks via WebSocket; receives text and audio events.
2. **Backend Gateway:** FastAPI service handling Auth, Rate Limiting, and Orchestration.
3. **Voice Pipeline:** A sequential orchestrator that chains ASR -> LLM -> TTS.
### 3.2 MVP Definition (In Scope)
- **[FR-01]** REST `/chat` (Text) and WebSocket `/ws` (Audio/Text) endpoints.
- **[FR-02]** In-memory rate limiting and "dev-token" validation.
- **[FR-03]** Local Mocks for all AI services (Transcribe, Bedrock, Polly).
- **[FR-04]** Automated AWS Deployment path in `us-east-1`.

---

## 4. Technical Specifications & API Design

### 4.1 System Architecture
```text
Browser -> [REST/WS] -> FastAPI (Gateway) -> VoicePipeline -> [Adapters] -> [AWS or Mock]
```

### 4.2 API Contracts
#### `POST /chat` (Stateless Text)
- **Request:** `{"text": string, "session_id": string}`
- **Response:** `{"reply": string, "provider": "pipeline"}`

#### `WS /ws` (Streaming Audio/Text)
- **Client Messages:** `{"type": "audio_chunk", "audio_base64": "..."}`
- **Server Messages:**
    - `{"type": "partial_text", "text": "..."}` (Streaming transcript)
    - `{"type": "bot_text", "text": "..."}` (Final LLM response)
    - `{"type": "bot_audio_chunk", "audio_base64": "..."}` (Generated speech)

---

## 5. Execution Plan (Implementation Tasks)

### 🧱 [WP-01] Backend Gateway & Protection
1. **Scaffold Service:** Implement FastAPI with `/health`, `/chat`, and `/ws` endpoints.
2. **Auth & Rate Limit:** Add `InMemoryRateLimiter` and token validation middleware.
3. **Schemas:** Define Pydantic models for all message envelopes.

### 🎙️ [WP-02] Adapter Pipeline & Orchestration
1. **Adapter Contracts:** Define `ASRAdapter`, `LLMAdapter`, and `TTSAdapter` interfaces.
2. **Implement Mocks:** Create local-only providers that return deterministic results.
3. **AWS Integration:** Implement AWS-backed providers (Transcribe, Bedrock, Polly) using `boto3`.
4. **Pipeline Logic:** Chain adapters in a thread-safe async pipeline.

### 🌐 [WP-03] Frontend Integration
1. **Audio Capture:** Implement `MediaRecorder` in the browser to stream PCM data.
2. **API Client:** Build a backend-only client that avoids direct AWS SDK usage.
3. **Interaction UI:** Create the `/index.html` shell for manual UAT.

### ☁️ [WP-04] AWS Bootstrap
1. **Containerization:** Create `Dockerfile` for the backend service.
2. **Infrastructure:** Write Terraform for ECR and a minimal ECS/Fargate task.
3. **Deployment Script:** Automate the build-push-deploy flow for `us-east-1`.

---

## 6. Verification & Quality Gates
- **Contract Tests:** `pytest tests/backend/test_backend_contracts.py`
- **Orchestration Tests:** `pytest tests/backend/test_orchestration_pipeline.py`
- **E2E Roundtrip:** `pytest tests/e2e/test_phase0_roundtrip.py`
- **Cloud Smoke Test:** `pytest tests/e2e/test_aws_dev_deploy_smoke.py`

---

## 7. Risks & Mitigations
| Risk | Probability | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **AWS Spend Burst** | Medium | High | Default to "Mock Mode" for all local development. |
| **High Latency** | High | Medium | Use "Partial Text" streaming events to provide immediate feedback. |
| **Token Expiry** | Low | Low | Implement retry-and-reconnect logic in the Frontend. |
