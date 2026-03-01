from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.asr import ASRAdapter
from backend.app.services.llm import LLMAdapter
from backend.app.services.tts import TTSAdapter


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"{stage} failed: {message}")
        self.stage = stage


@dataclass
class PipelineResult:
    transcript: str
    response_text: str
    response_audio: bytes


class VoicePipeline:
    def __init__(self, asr: ASRAdapter, llm: LLMAdapter, tts: TTSAdapter) -> None:
        self._asr = asr
        self._llm = llm
        self._tts = tts

    async def run_roundtrip(self, audio_bytes: bytes) -> PipelineResult:
        try:
            transcript = await self._asr.transcribe(audio_bytes)
        except Exception as exc:  # pragma: no cover - simple propagation guard
            raise PipelineStageError("asr", str(exc)) from exc

        try:
            response_text = await self._llm.generate(transcript)
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("llm", str(exc)) from exc

        try:
            response_audio = await self._tts.synthesize(response_text)
        except Exception as exc:  # pragma: no cover
            raise PipelineStageError("tts", str(exc)) from exc

        return PipelineResult(
            transcript=transcript,
            response_text=response_text,
            response_audio=response_audio,
        )

