from fastapi import APIRouter, Depends

from backend.app.schemas.messages import ChatRequest, ChatResponse
from backend.app.security.auth import require_token
from backend.app.security.rate_limit import enforce_http_rate_limit

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    _token: str = Depends(require_token),
    _rate_limit: None = Depends(enforce_http_rate_limit),
) -> ChatResponse:
    reply = f"echo: {payload.text}"
    return ChatResponse(reply=reply, provider="mock")
