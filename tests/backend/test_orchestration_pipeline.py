import asyncio
import unittest

from backend.app.orchestrator.pipeline import PipelineStageError, VoicePipeline
from backend.app.services.asr import ASRAdapter
from backend.app.services.llm import LLMAdapter
from backend.app.services.tts import TTSAdapter


class _RecordingASR(ASRAdapter):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def transcribe(self, audio_bytes: bytes) -> str:
        self.calls.append("asr")
        return "hello"


class _RecordingLLM(LLMAdapter):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def generate(self, text: str) -> str:
        self.calls.append("llm")
        return f"resp:{text}"


class _RecordingTTS(TTSAdapter):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def synthesize(self, text: str) -> bytes:
        self.calls.append("tts")
        return text.encode("utf-8")


class _FailingLLM(LLMAdapter):
    async def generate(self, text: str) -> str:
        raise RuntimeError("provider unavailable")


class _NoopASR(ASRAdapter):
    async def transcribe(self, audio_bytes: bytes) -> str:
        return "hello"


class _NoopTTS(TTSAdapter):
    async def synthesize(self, text: str) -> bytes:
        return b""


class OrchestrationPipelineTests(unittest.TestCase):
    def test_pipeline_runs_in_stt_llm_tts_order(self) -> None:
        calls: list[str] = []
        pipeline = VoicePipeline(
            asr=_RecordingASR(calls),
            llm=_RecordingLLM(calls),
            tts=_RecordingTTS(calls),
        )
        result = asyncio.run(pipeline.run_roundtrip(b"audio"))
        self.assertEqual(calls, ["asr", "llm", "tts"])
        self.assertEqual(result.transcript, "hello")
        self.assertEqual(result.response_text, "resp:hello")
        self.assertEqual(result.response_audio, b"resp:hello")

    def test_pipeline_reports_stage_failure(self) -> None:
        pipeline = VoicePipeline(asr=_NoopASR(), llm=_FailingLLM(), tts=_NoopTTS())
        with self.assertRaises(PipelineStageError) as ctx:
            asyncio.run(pipeline.run_roundtrip(b"audio"))
        self.assertEqual(ctx.exception.stage, "llm")


if __name__ == "__main__":
    unittest.main()

