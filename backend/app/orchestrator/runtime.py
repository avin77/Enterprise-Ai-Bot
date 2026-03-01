import os

from backend.app.orchestrator.pipeline import VoicePipeline
from backend.app.services.asr import ASRAdapter, AwsTranscribeAdapter, MockASRAdapter
from backend.app.services.aws_clients import build_aws_clients
from backend.app.services.llm import AwsBedrockAdapter, LLMAdapter, MockLLMAdapter
from backend.app.services.tts import AwsPollyAdapter, MockTTSAdapter, TTSAdapter


def _use_mocks() -> bool:
    return os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}


def build_pipeline() -> VoicePipeline:
    clients = build_aws_clients()
    if _use_mocks():
        asr: ASRAdapter = MockASRAdapter()
        llm: LLMAdapter = MockLLMAdapter()
        tts: TTSAdapter = MockTTSAdapter()
    else:
        asr = AwsTranscribeAdapter(clients)
        llm = AwsBedrockAdapter(clients)
        tts = AwsPollyAdapter(clients)
    return VoicePipeline(asr=asr, llm=llm, tts=tts)

