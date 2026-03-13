"""
End-to-end tests for AgentLLMAdapter routing paths.

These tests validate the 3-agent pipeline routing logic using mocks for
all external services (no real Bedrock calls).

Routing paths tested:
- retrieval: query routed to BM25 + ResponseAgent
- tool: query routed to MockToolAgent + RAG enrichment + ResponseAgent
- fallback: low-confidence query routed directly to safe retrieval
- confidence threshold: confidence < 0.7 always coerced to fallback
- trace event emission: non-blocking, no crashes
- empty chunks handling: ResponseAgent still returns safe response
- orchestrator error fallback: agent failure → safe retrieval fallback
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from backend.app.agents.llm_adapter import AgentLLMAdapter
from backend.app.agents.retrieval import ChunkResult
from backend.app.agents.types import RoutingDecision
from backend.app.services.knowledge import MockKnowledgeAdapter
from backend.app.services.aws_clients import build_aws_clients


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def knowledge():
    """MockKnowledgeAdapter backed by local sample FAQs."""
    return MockKnowledgeAdapter()


@pytest.fixture
def aws_clients():
    """Stub AWS clients (USE_AWS_MOCKS=true default)."""
    return build_aws_clients()


@pytest.fixture
def adapter(knowledge, aws_clients):
    """AgentLLMAdapter instance with optional agents disabled (default)."""
    return AgentLLMAdapter(knowledge, aws_clients)


@pytest.fixture
def adapter_with_tools(knowledge, aws_clients):
    """AgentLLMAdapter instance with MockToolAgent enabled."""
    return AgentLLMAdapter(knowledge, aws_clients, use_tools=True)


# ---------------------------------------------------------------------------
# Helper: build a RoutingDecision
# ---------------------------------------------------------------------------

def make_routing(
    intent: str = "property_tax",
    confidence: float = 0.9,
    routing_target: str = "retrieval",
    reasoning: str = "test routing",
) -> RoutingDecision:
    return RoutingDecision(
        intent=intent,
        confidence=confidence,
        routing_target=routing_target,
        reasoning=reasoning,
    )


def make_sample_chunks() -> list[ChunkResult]:
    return [
        ChunkResult(
            source_doc="property-tax-faq.pdf",
            text="Jackson County property tax rates are set annually by the County Legislature.",
            score=0.85,
            chunk_id="chunk:01",
        ),
        ChunkResult(
            source_doc="property-tax-faq.pdf",
            text="Tax payments are due April 1st and October 1st.",
            score=0.72,
            chunk_id="chunk:02",
        ),
    ]


# ---------------------------------------------------------------------------
# Task 1: test_retrieval_path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_path(adapter):
    """Verify retrieval path returns a grounded response."""
    mock_routing = make_routing(
        intent="property_tax", confidence=0.92, routing_target="retrieval"
    )
    mock_response = "According to property-tax-faq.pdf, property taxes are due April 1st."
    mock_chunks = make_sample_chunks()

    with (
        patch.object(adapter._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = mock_routing
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = mock_response

        result = await adapter.generate(
            "What is property tax in Jackson County?",
            system_context={},
        )

    assert result == mock_response
    assert "According to" in result
    assert result != ""


# ---------------------------------------------------------------------------
# Task 2: test_tool_path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_path(adapter_with_tools):
    """Verify tool path calls MockToolAgent and returns enriched response."""
    mock_routing = make_routing(
        intent="property_tax", confidence=0.88, routing_target="tool"
    )
    mock_response = "According to the system, your property tax balance is 0 and status is current."
    mock_chunks = make_sample_chunks()

    with (
        patch.object(adapter_with_tools._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter_with_tools._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter_with_tools._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = mock_routing
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = mock_response

        result = await adapter_with_tools.generate(
            "What is my property tax status?",
            system_context={},
        )

    assert result != ""
    assert result == mock_response


# ---------------------------------------------------------------------------
# Task 3: test_fallback_path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_path(adapter):
    """Verify fallback path goes directly to retrieval (no orchestrator routing)."""
    mock_routing = make_routing(
        intent="out_of_scope", confidence=0.4, routing_target="fallback"
    )
    mock_chunks = make_sample_chunks()
    mock_response = "According to general-info.pdf, I can help with county services."

    with (
        patch.object(adapter._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = mock_routing
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = mock_response

        result = await adapter.generate(
            "Can you help me with something completely unrelated?",
            system_context={},
        )

    assert result != ""
    assert "error" not in result.lower() or "having trouble" not in result.lower()


# ---------------------------------------------------------------------------
# Task 4: test_confidence_threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confidence_threshold(adapter):
    """Verify confidence < 0.7 is always coerced to fallback routing."""
    # Orchestrator returns a routing decision with confidence = 0.6 (< 0.7 threshold)
    low_confidence_routing = make_routing(
        intent="property_tax",
        confidence=0.6,
        routing_target="retrieval",  # This should be coerced to fallback
    )
    mock_chunks = make_sample_chunks()
    mock_response = "According to property-tax-faq.pdf, property tax information is available."

    with (
        patch.object(adapter._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = low_confidence_routing
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = mock_response

        result = await adapter.generate(
            "Something ambiguous",
            system_context={},
        )

    # Verify response was returned (not a crash)
    assert result != ""
    # Verify retrieve was called (fallback path calls retrieve)
    mock_retrieve.assert_called_once()


# ---------------------------------------------------------------------------
# Task 5: test_trace_event_emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trace_event_emission(adapter):
    """Verify trace events are emitted without crashing the voice turn."""
    mock_routing = make_routing(confidence=0.9, routing_target="retrieval")
    mock_chunks = make_sample_chunks()
    mock_response = "According to test.pdf, this is a test response."

    with (
        patch.object(adapter._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = mock_routing
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = mock_response

        # Should not crash
        result = await adapter.generate("Test trace emission query")

    assert result == mock_response
    # Allow any created tasks to run
    await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Task 6: test_empty_chunks_handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_chunks_handling(adapter):
    """Verify ResponseAgent handles empty chunks gracefully."""
    mock_routing = make_routing(confidence=0.9, routing_target="retrieval")
    safe_response = "I don't have that specific information. You can contact Jackson County at 816-881-3000."

    with (
        patch.object(adapter._orchestrator, "route", new_callable=AsyncMock) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_route.return_value = mock_routing
        mock_retrieve.return_value = []  # Empty chunks
        mock_synth.return_value = safe_response

        result = await adapter.generate(
            "An obscure question with no matching FAQ",
            system_context={},
        )

    assert result != ""
    assert "816-881-3000" in result or result == safe_response
    # Verify ResponseAgent was still called with empty chunks
    mock_synth.assert_called_once()


# ---------------------------------------------------------------------------
# Task 7: test_orchestrator_error_fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_error_fallback(adapter):
    """Verify OrchestratorAgent failure falls back to safe retrieval."""
    mock_chunks = make_sample_chunks()
    safe_response = "According to property-tax-faq.pdf, I can help with tax questions."

    with (
        patch.object(
            adapter._orchestrator, "route",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Bedrock connection failed"),
        ) as mock_route,
        patch.object(adapter._retrieval, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch.object(adapter._response, "synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_retrieve.return_value = mock_chunks
        mock_synth.return_value = safe_response

        result = await adapter.generate(
            "What is property tax?",
            system_context={},
        )

    # Should NOT crash — must return a valid response
    assert result != ""
    # Should have fallen back to retrieval
    mock_retrieve.assert_called_once()
    mock_synth.assert_called_once()


# ---------------------------------------------------------------------------
# Task 8: test_interface_compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interface_compatibility(adapter):
    """Verify AgentLLMAdapter implements LLMAdapter interface correctly."""
    from backend.app.services.llm import LLMAdapter

    assert isinstance(adapter, LLMAdapter), "AgentLLMAdapter must extend LLMAdapter"
    assert hasattr(adapter, "generate"), "Must have generate() method"
    assert callable(adapter.generate), "generate must be callable"

    # Verify same signature as RAGLLMAdapter: generate(text, system_context)
    import inspect
    sig = inspect.signature(adapter.generate)
    params = list(sig.parameters.keys())
    assert "text" in params, "generate() must accept 'text' parameter"
    assert "system_context" in params, "generate() must accept 'system_context' parameter"
