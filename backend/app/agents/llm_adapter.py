"""
AgentLLMAdapter — implements LLMAdapter interface via 3-agent pipeline.

Phase 1.5: Drop-in replacement for RAGLLMAdapter. Controlled by USE_AGENTS env var.

Pipeline:
    OrchestratorAgent  → routes query (intent + confidence + routing_target)
    RetrievalAgent     → BM25 retrieval (same as Phase 1, no latency change)
    ResponseAgent      → Claude Sonnet synthesis with grounding + guardrails

Routing paths:
    retrieval  → RetrievalAgent → ResponseAgent
    tool       → MockToolAgent → RetrievalAgent (enrichment) → ResponseAgent
    fallback   → RetrievalAgent (direct, no orchestrator) → ResponseAgent

Rollback:
    Set USE_AGENTS=false to instantly revert to RAGLLMAdapter — no code redeploy.

Error handling:
    Any agent failure falls back to safe retrieval. Voice turns never crash.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from backend.app.agents.memory import MockMemoryStore
from backend.app.agents.orchestrator import OrchestratorAgent
from backend.app.agents.response import ResponseAgent
from backend.app.agents.retrieval import ChunkResult, RetrievalAgent
from backend.app.agents.tool import MockToolAgent
from backend.app.agents.tracer import emit_trace_event
from backend.app.agents.types import RoutingDecision
from backend.app.services.aws_clients import AwsClientBundle
from backend.app.services.knowledge import KnowledgeAdapter
from backend.app.services.llm import LLMAdapter

logger = logging.getLogger(__name__)


def _detect_grounding(response_text: str) -> tuple[bool, str]:
    """Simple pattern-based grounding detection for Phase 1.5.

    Phase 3 will upgrade to LLM judge for grounding evaluation.

    Returns
    -------
    (grounded, grounding_signal) tuple.
    """
    if "According to" in response_text or "according to" in response_text:
        return True, "has_source_attribution"
    if "I don't have" in response_text or "I don't have" in response_text:
        return False, "no_sources"
    if "I'm having trouble" in response_text:
        return False, "error_response"
    return True, "ambiguous"


class AgentLLMAdapter(LLMAdapter):
    """Multi-agent pipeline implementing the LLMAdapter interface.

    Drop-in replacement for RAGLLMAdapter — same generate() signature.

    Parameters
    ----------
    knowledge_adapter:
        KnowledgeAdapter used by RetrievalAgent for BM25 retrieval.
    aws_clients:
        AwsClientBundle used by OrchestratorAgent and ResponseAgent.
    use_memory:
        If True, instantiate MockMemoryStore (Phase 2.5: DynamoDB memory).
    use_tools:
        If True, instantiate MockToolAgent (Phase 5: real tool APIs).
    """

    def __init__(
        self,
        knowledge_adapter: KnowledgeAdapter,
        aws_clients: AwsClientBundle,
        use_memory: bool = False,
        use_tools: bool = False,
    ) -> None:
        self._knowledge = knowledge_adapter
        self._clients = aws_clients

        # Core agents
        self._orchestrator = OrchestratorAgent(aws_clients)
        self._retrieval = RetrievalAgent(knowledge_adapter)
        self._response = ResponseAgent(aws_clients)

        # Optional agents
        self._memory: Optional[MockMemoryStore] = MockMemoryStore() if use_memory else None
        self._tool: Optional[MockToolAgent] = MockToolAgent() if use_tools else None

    async def generate(self, text: str, system_context: str = "") -> str:
        """Orchestrate the 3-agent pipeline and return a grounded response.

        Parameters
        ----------
        text:
            User's transcribed utterance.
        system_context:
            Unused in AgentLLMAdapter (context is built internally via agents).
            Kept for interface compatibility with RAGLLMAdapter.

        Returns
        -------
        Grounded response string. Falls back gracefully on any agent failure.
        """
        turn_start = time.monotonic()
        turn_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())  # No session tracking in Phase 1.5

        # Default routing decision (used if orchestrator fails)
        routing_decision = RoutingDecision(
            intent="error",
            confidence=0.0,
            routing_target="fallback",
            reasoning="Default fallback",
        )
        chunks: list[ChunkResult] = []
        tool_calls: list[dict] = []
        llm_latency_ms = 0
        fallback_triggered = False

        try:
            # Step 1: Route the query (skip if orchestrator fails → fallback)
            orchestrator_start = time.monotonic()
            try:
                routing_decision = await self._orchestrator.route(text, history=[])

                # Enforce low-confidence fallback (belt-and-suspenders: orchestrator also
                # enforces this, but we check here too for safety)
                if routing_decision.confidence < 0.7:
                    routing_decision.routing_target = "fallback"
                    fallback_triggered = True

                logger.info(
                    "AgentLLMAdapter: routed query to=%s intent=%s confidence=%.2f",
                    routing_decision.routing_target,
                    routing_decision.intent,
                    routing_decision.confidence,
                )
            except Exception as exc:
                logger.error(
                    "AgentLLMAdapter: OrchestratorAgent.route() failed: %s — using fallback",
                    exc,
                )
                routing_decision.routing_target = "fallback"
                fallback_triggered = True

            orchestrator_latency_ms = int((time.monotonic() - orchestrator_start) * 1000)

            # Step 2: Execute the routing path
            response_start = time.monotonic()

            if routing_decision.routing_target == "tool" and self._tool is not None:
                # Tool path: call MockToolAgent, enrich with RAG chunks, synthesize
                response_text = await self._execute_tool_path(
                    text=text,
                    routing_decision=routing_decision,
                    chunks_out=chunks,
                    tool_calls_out=tool_calls,
                )
            elif routing_decision.routing_target == "retrieval":
                # Retrieval path: BM25 → ResponseAgent
                response_text = await self._execute_retrieval_path(
                    text=text,
                    routing_decision=routing_decision,
                    chunks_out=chunks,
                )
            else:
                # Fallback path (low confidence, out-of-scope, tool disabled, etc.)
                fallback_triggered = True
                response_text = await self._execute_fallback_path(
                    text=text,
                    chunks_out=chunks,
                )

            llm_latency_ms = int((time.monotonic() - response_start) * 1000)

        except Exception as exc:
            # Last-resort error handling — always return something
            logger.error(
                "AgentLLMAdapter.generate(): unexpected error for query=%r: %s",
                text[:80],
                exc,
            )
            response_text = (
                "I'm having trouble processing that request. Please try again."
            )
            fallback_triggered = True

        total_latency_ms = int((time.monotonic() - turn_start) * 1000)

        # Step 3: Emit trace event (fire-and-forget, non-blocking)
        grounded, grounding_signal = _detect_grounding(response_text)
        retrieved_doc_ids = [c.chunk_id for c in chunks]

        try:
            asyncio.create_task(
                emit_trace_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    intent=routing_decision.intent,
                    intent_confidence=routing_decision.confidence,
                    routing_target=routing_decision.routing_target,
                    retrieved_doc_ids=retrieved_doc_ids,
                    llm_prompt_tokens=0,   # Token counts require Bedrock response introspection (Phase 3)
                    llm_response_tokens=0,
                    llm_latency_ms=llm_latency_ms,
                    tool_calls=tool_calls,
                    total_latency_ms=total_latency_ms,
                    fallback_triggered=fallback_triggered,
                    grounded=grounded,
                    grounding_signal=grounding_signal,
                )
            )
        except Exception as exc:
            # Trace emission failures must never crash voice turns
            logger.error("AgentLLMAdapter: trace emission setup failed: %s", exc)

        return response_text

    # ---------------------------------------------------------------------------
    # Private routing path methods
    # ---------------------------------------------------------------------------

    async def _execute_retrieval_path(
        self,
        text: str,
        routing_decision: RoutingDecision,
        chunks_out: list[ChunkResult],
    ) -> str:
        """Retrieval path: BM25 retrieval → ResponseAgent synthesis."""
        chunks = await self._retrieval.retrieve(
            text, intent=routing_decision.intent, top_k=3
        )
        chunks_out.extend(chunks)

        return await self._response.synthesize(text, chunks)

    async def _execute_tool_path(
        self,
        text: str,
        routing_decision: RoutingDecision,
        chunks_out: list[ChunkResult],
        tool_calls_out: list[dict],
    ) -> str:
        """Tool path: MockToolAgent + RAG enrichment → ResponseAgent synthesis."""
        # Execute tool
        tool_result = await self._tool.execute(routing_decision.intent, {})
        tool_calls_out.append({
            "tool_name": tool_result.tool_name,
            "success": tool_result.success,
            "latency_ms": tool_result.latency_ms,
        })

        # Enrich with top-3 RAG chunks
        chunks = await self._retrieval.retrieve(
            text, intent=routing_decision.intent, top_k=3
        )
        chunks_out.extend(chunks)

        # Inject tool data into query for ResponseAgent
        if tool_result.success:
            enriched_query = (
                f"{text}\n\n"
                f"[Tool data for {tool_result.tool_name}: "
                f"{json.dumps(tool_result.data)}]"
            )
        else:
            enriched_query = text

        return await self._response.synthesize(enriched_query, chunks)

    async def _execute_fallback_path(
        self,
        text: str,
        chunks_out: list[ChunkResult],
    ) -> str:
        """Fallback path: direct BM25 retrieval (no orchestrator routing)."""
        chunks = await self._retrieval.retrieve(text, intent="", top_k=3)
        chunks_out.extend(chunks)

        return await self._response.synthesize(text, chunks)
