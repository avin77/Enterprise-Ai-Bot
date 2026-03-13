from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import uuid4

from backend.app.services.asr import ASRAdapter
from backend.app.services.llm import LLMAdapter
from backend.app.services.tts import TTSAdapter

# Design note: Conversation tracking is NOT done inside VoicePipeline -- it's done in the
# WebSocket handler (main.py) after the pipeline result is returned. This keeps pipeline.py
# pure (no side effects) and testable without DynamoDB.

# Trace emission: fire-and-forget via asyncio.create_task() — never blocks voice turn.
try:
    from backend.app.agents.tracer import emit_trace_event as _emit_trace_event
    _TRACER_AVAILABLE = True
except ImportError:
    _TRACER_AVAILABLE = False

# Grounding detection patterns (Phase 1.5 — simple pattern match; LLM judge added in Phase 3)
_GROUNDED_PATTERN = re.compile(r"according to", re.IGNORECASE)
_UNGROUNDED_PATTERN = re.compile(r"i don.t have", re.IGNORECASE)


def _detect_grounding(response_text: str) -> tuple[bool, str]:
    """
    Detect whether the response cites sources.

    Returns:
        (grounded, grounding_signal) tuple.
        grounding_signal is one of: has_source_attribution | no_sources | ambiguous
    """
    if _GROUNDED_PATTERN.search(response_text):
        return True, "has_source_attribution"
    if _UNGROUNDED_PATTERN.search(response_text):
        return False, "no_sources"
    return True, "ambiguous"


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"{stage} failed: {message}")
        self.stage = stage


@dataclass
class PipelineResult:
    transcript: str
    response_text: str
    response_audio: bytes
    asr_ms: float = 0.0
    rag_ms: float = 0.0
    llm_ms: float = 0.0
    tts_ms: float = 0.0
    sources: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    top_score: float = 0.0


class VoicePipeline:
    def __init__(
        self,
        asr: ASRAdapter,
        llm: LLMAdapter,
        tts: TTSAdapter,
        knowledge: Optional[object] = None,
        session_id: str = "",
    ) -> None:
        self._asr = asr
        self._llm = llm
        self._tts = tts
        self._knowledge = knowledge  # KnowledgeAdapter | None
        self._session_id = session_id or str(uuid4())

    def _fire_trace(
        self,
        turn_id: str,
        chunk_ids: List[str],
        llm_ms: float,
        total_ms: float,
        fallback_triggered: bool,
        response_text: str,
    ) -> None:
        """
        Emit trace event as fire-and-forget asyncio task.
        Never raises — trace failures must not affect voice turns.
        """
        if not _TRACER_AVAILABLE:
            return
        try:
            grounded, grounding_signal = _detect_grounding(response_text)
            asyncio.create_task(
                _emit_trace_event(
                    session_id=self._session_id,
                    turn_id=turn_id,
                    intent="unknown",              # Phase 1.5: intent routing is in AgentLLMAdapter
                    intent_confidence=0.0,         # populated by AgentLLMAdapter in Phase 1.5
                    routing_target="retrieval",    # pipeline always uses retrieval path
                    retrieved_doc_ids=chunk_ids,
                    llm_prompt_tokens=0,           # token counting via Bedrock response metadata
                    llm_response_tokens=0,
                    llm_latency_ms=int(llm_ms),
                    tool_calls=[],
                    total_latency_ms=int(total_ms),
                    fallback_triggered=fallback_triggered,
                    grounded=grounded,
                    grounding_signal=grounding_signal,
                )
            )
        except RuntimeError:
            # No running event loop (e.g. sync test context) — emit directly is not possible.
            # Silently skip rather than crash.
            pass
        except Exception:
            # Best-effort — never propagate trace errors
            pass

    async def run_roundtrip(self, audio_bytes: bytes, session_id: str = "") -> PipelineResult:
        turn_id = str(uuid4())
        turn_start = time.monotonic()

        if session_id:
            self._session_id = session_id

        try:
            t0 = time.monotonic()
            transcript = await self._asr.transcribe(audio_bytes)
            asr_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover - simple propagation guard
            raise PipelineStageError("asr", str(exc)) from exc

        # RAG stage: retrieve knowledge chunks between ASR and LLM
        sources: List[str] = []
        chunk_ids: List[str] = []
        top_score = 0.0
        system_context = ""
        t0 = time.monotonic()
        if self._knowledge is not None:
            try:
                knowledge_result = await self._knowledge.retrieve(transcript, top_k=3)
                sources = knowledge_result.sources
                chunk_ids = knowledge_result.chunk_ids
                top_score = knowledge_result.top_score
                if knowledge_result.chunks:
                    system_context = "\n\n".join([
                        f"[Source: {src}]\n{chunk}"
                        for chunk, src in zip(knowledge_result.chunks, knowledge_result.sources)
                    ])
            except Exception:  # pragma: no cover
                pass  # RAG failure must never block voice response
        rag_ms = max((time.monotonic() - t0) * 1000, 0.001)

        try:
            t0 = time.monotonic()
            response_text = await self._llm.generate(transcript, system_context=system_context)
            llm_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("llm", str(exc)) from exc

        try:
            t0 = time.monotonic()
            response_audio = await self._tts.synthesize(response_text)
            tts_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("tts", str(exc)) from exc

        total_ms = (time.monotonic() - turn_start) * 1000

        # Emit trace event fire-and-forget — never blocks voice response
        self._fire_trace(
            turn_id=turn_id,
            chunk_ids=chunk_ids,
            llm_ms=llm_ms,
            total_ms=total_ms,
            fallback_triggered=False,
            response_text=response_text,
        )

        return PipelineResult(
            transcript=transcript,
            response_text=response_text,
            response_audio=response_audio,
            asr_ms=asr_ms,
            rag_ms=rag_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
            sources=sources,
            chunk_ids=chunk_ids,
            top_score=top_score,
        )

    async def run_text_turn(self, text: str, session_id: str = "") -> PipelineResult:
        turn_id = str(uuid4())
        turn_start = time.monotonic()

        if session_id:
            self._session_id = session_id

        # RAG stage
        sources: List[str] = []
        chunk_ids: List[str] = []
        top_score = 0.0
        system_context = ""
        t0 = time.monotonic()
        if self._knowledge is not None:
            try:
                knowledge_result = await self._knowledge.retrieve(text, top_k=3)
                sources = knowledge_result.sources
                chunk_ids = knowledge_result.chunk_ids
                top_score = knowledge_result.top_score
                if knowledge_result.chunks:
                    system_context = "\n\n".join([
                        f"[Source: {src}]\n{chunk}"
                        for chunk, src in zip(knowledge_result.chunks, knowledge_result.sources)
                    ])
            except Exception:  # pragma: no cover
                pass
        rag_ms = max((time.monotonic() - t0) * 1000, 0.001)

        try:
            t0 = time.monotonic()
            response_text = await self._llm.generate(text, system_context=system_context)
            llm_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("llm", str(exc)) from exc

        try:
            t0 = time.monotonic()
            response_audio = await self._tts.synthesize(response_text)
            tts_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("tts", str(exc)) from exc

        total_ms = (time.monotonic() - turn_start) * 1000

        # Emit trace event fire-and-forget — never blocks voice response
        self._fire_trace(
            turn_id=turn_id,
            chunk_ids=chunk_ids,
            llm_ms=llm_ms,
            total_ms=total_ms,
            fallback_triggered=False,
            response_text=response_text,
        )

        return PipelineResult(
            transcript=text,
            response_text=response_text,
            response_audio=response_audio,
            asr_ms=0.0,
            rag_ms=rag_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
            sources=sources,
            chunk_ids=chunk_ids,
            top_score=top_score,
        )
