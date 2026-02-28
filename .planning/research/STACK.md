# Stack Research

**Domain:** Gov-ready web voice AI assistant
**Researched:** 2026-02-28
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python FastAPI | Current stable 0.x | Core API/orchestrator runtime | High productivity, async support, strong ecosystem for service adapters |
| AWS ECS Fargate | Current platform release | Stateless orchestrator hosting | Managed container runtime with predictable scaling and IAM integration |
| Amazon API Gateway (REST + WebSocket) | Managed service | Public ingress and WS transport | Native AWS auth/WAF integration and mature API governance |
| Amazon Bedrock (Claude Sonnet + Haiku) | Current model versions | Primary response generation + supervisor review | Supports policy-aware LLM orchestration with managed security controls |
| OpenSearch Serverless + Titan embeddings | Current service/API versions | Hybrid retrieval with citations | Enables keyword + vector retrieval with manageable operational overhead |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| OpenTelemetry SDK | Current stable | Distributed tracing and metrics correlation | Required for end-to-end latency and reliability observability |
| Pydantic | Current stable | Request/response schema validation | Use for strict contract and config validation |
| Redis client for Python | Current stable | Session context read/write | Use for short-lived transcript/tool context persistence |
| AWS SDK for Python (boto3) | Current stable | Service integrations | Use for Bedrock, S3, Secrets Manager, and other AWS calls |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Terraform + tfsec + checkov | IaC provisioning and policy scanning | Required to keep infrastructure reproducible and auditable |
| Pre-commit + lint/test tooling | Local quality gates | Enforce consistency before CI |
| Docker Compose | Local integration harness | Mock cloud dependencies for fast developer feedback |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| ECS Fargate | EKS | Use EKS only if workload/custom scheduling needs exceed Fargate simplicity |
| OpenSearch Serverless | Self-managed vector DB | Use only if strict feature/cost constraints justify increased ops burden |
| API Gateway WS | Self-hosted WebSocket gateway | Use only if custom protocol control is required beyond API Gateway features |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Unbounded tool execution | Creates policy and cost risk | Supervisor-gated, schema-validated tool calls |
| Ad hoc logging with raw payloads | Leaks sensitive data and hurts compliance | Structured JSON logs with redaction and sampling |
| Premature multi-region architecture | Adds complexity before MVP fit | Single-region with tested recovery runbook |

## Sources

- PLAN.md in repository - project constraints and target architecture

---
*Stack research for: Gov-ready web voice AI assistant*
*Researched: 2026-02-28*
