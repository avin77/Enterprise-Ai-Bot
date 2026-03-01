from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    provider: str = "mock"


class WsClientMessage(BaseModel):
    type: Literal["start", "audio_chunk", "text", "end"]
    text: str | None = None
    audio_base64: str | None = None


class WsServerMessage(BaseModel):
    type: Literal["ack", "partial_text", "bot_text", "bot_audio_chunk", "error"]
    text: str | None = None
    audio_base64: str | None = None
    error: str | None = None

