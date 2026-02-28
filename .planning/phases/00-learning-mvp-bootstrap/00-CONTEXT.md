# Phase 0: Learning MVP Bootstrap - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver one full working voice roundtrip for MVP validation with a layered architecture and an initial AWS deployment path in us-east-1.

</domain>

<decisions>
## Implementation Decisions

### Layered Architecture (Locked)
- Frontend layer captures microphone input and sends data to backend only.
- Frontend uses WebSocket for streaming and REST for non-streaming interactions.
- Frontend must not call AWS services directly and must not store cloud credentials.

### Backend API Surface (Locked)
- Backend is the core integration layer.
- Backend must expose `/ws`, `/chat`, and `/health`.
- Backend must include MVP-level API protection: token validation + rate limiting.

### AWS Service Usage (Locked)
- Backend calls AWS services securely for voice pipeline:
  - Amazon Transcribe for speech-to-text
  - Amazon Bedrock for LLM response generation
  - Amazon Polly for text-to-speech
- Backend credential handling uses IAM role and environment variables.
- Secrets/keys are never exposed to frontend.

### Adapter Layer (Locked)
- Keep ASR, LLM, and TTS adapters as abstraction boundary.
- Adapter design must permit future provider switches (Azure, Google, on-prem) without frontend changes.

### Infrastructure Layer (Locked for Phase 0 Scope)
- Backend is containerized with Docker.
- Initial AWS deployment path includes ECR and ECS/Fargate target in us-east-1.
- Infrastructure is defined through Terraform for phase-0 delivery.

### Claude's Discretion
- Exact token format for MVP auth validation.
- Exact message envelope fields beyond required endpoint contract.
- Exact implementation details of local mocks and smoke tests.

</decisions>

<specifics>
## Specific Ideas

- Phase 0 should move fast but still prove cloud viability on AWS.
- Secure roundtrip means backend-mediated AWS calls only.
- Backend is the orchestration core: audio -> STT -> LLM -> TTS -> streamed response.

</specifics>

<deferred>
## Deferred Ideas

- Full authentication system and complete IAM hardening.
- Production observability suite and full compliance controls.
- Multi-region deployment, advanced autoscaling, and complex networking.

</deferred>

---

*Phase: 00-learning-mvp-bootstrap*
*Context gathered: 2026-02-28*