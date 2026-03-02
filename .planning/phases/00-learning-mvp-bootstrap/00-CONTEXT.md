# Phase 0: Learning MVP Bootstrap - Context

**Gathered:** 2026-03-01
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
- "Deploy path: Dockerfile -> ECR -> ECS Task/Service -> CloudWatch Logs" means a real AWS deployment path, not local-only execution.
- Phase-0 Terraform provisions deploy assets by default and can run service deployment when VPC subnet/security-group inputs are provided.

### AWS API Exposure (Locked for Phase 0 Scope)
- Public app APIs are FastAPI endpoints (`/health`, `/chat`, `/ws`) running in the backend service.
- AWS API Gateway is not required for phase-0 acceptance; it is a later hardening/scaling step.
- If deployed in AWS in phase 0, endpoint exposure is via ECS service networking path (and optional load balancer additions later).

### API Contract Readability (Locked)
- `/health`, `/chat`, and `/ws` contracts must be documented with explicit input/output examples.
- Every API must include acceptance criteria and manual verification steps that TPMs can run without code changes.
- API docs should explain why each endpoint exists in business terms, not only implementation terms.

### Data Handling Transparency (Locked)
- Phase 0 does not introduce persistent application data storage (no database yet).
- Runtime interaction data is handled in-memory for the active request/session path.
- Documentation must clearly call out what is and is not stored, and where observability happens.

### Stakeholder Documentation (Locked)
- Produce a single PRD-style phase document for mixed audience: TPM, engineering manager, and data scientist.
- Include high-level architecture, glossary for technical terms, NFRs, and test strategy.
- Keep phase 0 scope fixed; future requirements are listed as deferred.

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
- Documentation should let non-technical stakeholders understand what is built, why it matters, and how to validate it.
- Include API-level user stories and acceptance criteria linked back to phase plans.

</specifics>

<deferred>
## Deferred Ideas

- Full authentication system and complete IAM hardening.
- Production observability suite and full compliance controls.
- Multi-region deployment, advanced autoscaling, and complex networking.
- Persistent conversation/session storage for analytics and replay.
- Production-grade cost instrumentation per API call.
- Add persistent AWS database for conversation/session storage (e.g., DynamoDB/RDS) plus retention policy.
- Add AWS API Gateway + custom domain + versioning/governance for enterprise API management.

</deferred>

---

*Phase: 00-learning-mvp-bootstrap*
*Context gathered: 2026-03-01*
