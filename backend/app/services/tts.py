from __future__ import annotations

from abc import ABC, abstractmethod
from base64 import b64encode

from backend.app.services.aws_clients import AwsClientBundle


class TTSAdapter(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError


class MockTTSAdapter(TTSAdapter):
    async def synthesize(self, text: str) -> bytes:
        return b64encode(text.encode("utf-8"))


class AwsPollyAdapter(TTSAdapter):
    def __init__(self, clients: AwsClientBundle, voice_id: str = "Joanna") -> None:
        self._clients = clients
        self._voice_id = voice_id

    async def synthesize(self, text: str) -> bytes:
        if not text:
            return b""
        return b64encode(f"aws-audio:{text}".encode("utf-8"))

