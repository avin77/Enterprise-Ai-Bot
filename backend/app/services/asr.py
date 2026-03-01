from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.services.aws_clients import AwsClientBundle


class ASRAdapter(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        raise NotImplementedError


class MockASRAdapter(ASRAdapter):
    async def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        return "transcript:" + str(len(audio_bytes))


class AwsTranscribeAdapter(ASRAdapter):
    def __init__(self, clients: AwsClientBundle) -> None:
        self._clients = clients

    async def transcribe(self, audio_bytes: bytes) -> str:
        # Phase 0 keeps AWS integration lightweight; full streaming transcription comes later.
        if not audio_bytes:
            return ""
        return "aws-transcript:" + str(len(audio_bytes))

