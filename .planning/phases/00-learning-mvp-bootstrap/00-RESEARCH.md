# Phase 0: Learning MVP Bootstrap - Research

**Researched:** 2026-02-28
**Domain:** Streaming voice MVP bootstrap (FastAPI + browser WebSocket)
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

No user constraints - all decisions at Claude's discretion.
</user_constraints>

<research_summary>
## Summary

This phase should optimize for fastest path to a working one-turn voice loop while keeping extension points for later hardening phases. The most reliable path is a local-first setup with mockable ASR/LLM/TTS adapters, a single WebSocket contract, and a minimal browser client.

The plan should avoid over-engineering: defer cloud deployment, IAM, and production observability details to later phases already defined in the roadmap. In this phase, success is a repeatable local demo with clear adapter boundaries.

**Primary recommendation:** Build a local FastAPI WebSocket service with pluggable mock adapters and a minimal browser test client, verified by automated smoke tests.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3.11+ | current | Runtime for backend services | Matches project direction and async support |
| FastAPI | current | HTTP + WebSocket backend framework | Fast setup and solid async ergonomics |
| Uvicorn | current | ASGI server | Standard FastAPI runtime |
| Browser Web APIs | native | Audio capture + WS client | Lowest-friction MVP client path |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | current | Automated smoke and unit tests | Validate bootstrap and one-turn flow |
| pydantic | current | Message envelope validation | Keep WS contract stable early |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI WS | API Gateway WS early | Slower local iteration and more setup overhead |
| Real ASR/TTS providers in phase 0 | Mock adapters | Mocks reduce early integration cost/risk |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
backend/
|-- app/
|   |-- main.py
|   |-- ws/voice.py
|   |-- orchestrator/streaming.py
|   `-- services/{asr,llm,tts}.py
frontend/
|-- index.html
`-- app.js
tests/
|-- backend/
`-- e2e/
```

### Pattern 1: Adapter-First Streaming Pipeline
**What:** Keep ASR/LLM/TTS behind stable interfaces and compose them in one orchestrator stream.
**When to use:** Early MVP where providers may change later.

### Pattern 2: Contract-First WebSocket Envelopes
**What:** Standardize message types (`start`, `audio_chunk`, `partial_text`, `bot_text`, `bot_audio_chunk`, `end`, `error`).
**When to use:** Any bidirectional streaming flow.

### Anti-Patterns to Avoid
- Mixing provider SDK logic directly in WebSocket handler.
- Building production auth/deployment complexity in this phase.
- Skipping automated smoke verification for one-turn flow.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket protocol parsing | Custom ad hoc string parsing | Typed JSON envelopes | Reduces protocol drift and bugs |
| Streaming orchestration state machine from scratch | Large custom engine | Small async generator pipeline | Enough for MVP and easier to test |
| End-to-end verification by manual clicks only | Manual-only checks | pytest smoke + e2e harness | Repeatability for later phases |
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Latency hidden by synchronous chaining
**What goes wrong:** First response appears only after full pipeline completes.
**Why it happens:** Orchestrator waits for final LLM output before any emission.
**How to avoid:** Emit partial text/audio progressively from async stream.
**Warning signs:** No intermediate events before final payload.

### Pitfall 2: Tight coupling to one provider SDK
**What goes wrong:** Refactors become expensive when swapping providers.
**Why it happens:** WS handler calls provider APIs directly.
**How to avoid:** Use adapter interfaces and dependency wiring.
**Warning signs:** Provider-specific types leak into route layer.

### Pitfall 3: Demo-only flow without regression checks
**What goes wrong:** Small changes silently break one-turn demo.
**Why it happens:** No automated one-turn smoke test.
**How to avoid:** Add backend + e2e smoke tests in this phase.
**Warning signs:** Repeated manual fixes before every demo.
</common_pitfalls>

<open_questions>
## Open Questions

1. **Audio format for initial client chunks**
   - What we know: Browser capture and chunk streaming is required.
   - What's unclear: Exact MVP format (PCM16 vs Opus) for first implementation.
   - Recommendation: Start with simplest stable format, abstract in adapter.

2. **Local mock fidelity level**
   - What we know: Mocks are needed for phase speed.
   - What's unclear: How realistic they should be for latency behavior.
   - Recommendation: Keep deterministic mocks first, add latency simulation later.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- .planning/ROADMAP.md - phase goal, dependencies, success criteria
- .planning/REQUIREMENTS.md - VOIC-01 and VOIC-02 coverage
- PLAN.md - architecture direction and constraints

### Secondary (MEDIUM confidence)
- Existing project planning docs under `.planning/`
</sources>

---

*Phase: 00-learning-mvp-bootstrap*
*Research completed: 2026-02-28*
*Ready for planning: yes*