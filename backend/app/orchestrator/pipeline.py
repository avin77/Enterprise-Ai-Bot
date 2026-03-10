from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from backend.app.services.asr import ASRAdapter
from backend.app.services.llm import LLMAdapter
from backend.app.services.tts import TTSAdapter

# Design note: Conversation tracking is NOT done inside VoicePipeline — it's done in the
# WebSocket handler (main.py) after the pipeline result is returned. This keeps pipeline.py
# pure (no side effects) and testable without DynamoDB.


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
    def __init__(self, asr: ASRAdapter, llm: LLMAdapter, tts: TTSAdapter) -> None:
        self._asr = asr
        self._llm = llm
        self._tts = tts

    async def run_roundtrip(self, audio_bytes: bytes) -> PipelineResult:
        try:
            t0 = time.monotonic()
            transcript = await self._asr.transcribe(audio_bytes)
            asr_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover - simple propagation guard
            raise PipelineStageError("asr", str(exc)) from exc

        try:
            t0 = time.monotonic()
            response_text = await self._llm.generate(transcript)
            llm_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("llm", str(exc)) from exc

        try:
            t0 = time.monotonic()
            response_audio = await self._tts.synthesize(response_text)
            tts_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("tts", str(exc)) from exc

        return PipelineResult(
            transcript=transcript,
            response_text=response_text,
            response_audio=response_audio,
            asr_ms=asr_ms,
            rag_ms=0.0,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
        )

    async def run_text_turn(self, text: str) -> PipelineResult:
        try:
            t0 = time.monotonic()
            response_text = await self._llm.generate(text)
            llm_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("llm", str(exc)) from exc

        try:
            t0 = time.monotonic()
            response_audio = await self._tts.synthesize(response_text)
            tts_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("tts", str(exc)) from exc

        return PipelineResult(
            transcript=text,
            response_text=response_text,
            response_audio=response_audio,
            asr_ms=0.0,
            rag_ms=0.0,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
        )
