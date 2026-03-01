from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.services.aws_clients import AwsClientBundle


class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, text: str) -> str:
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    async def generate(self, text: str) -> str:
        return f"assistant:{text}"


class AwsBedrockAdapter(LLMAdapter):
    def __init__(self, clients: AwsClientBundle, model_id: str | None = None) -> None:
        self._clients = clients
        self._model_id = model_id or "anthropic.claude-3-haiku-20240307-v1:0"

    async def generate(self, text: str) -> str:
        if not text:
            return ""
        return f"aws-assistant:{text}"

