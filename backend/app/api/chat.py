from fastapi import APIRouter, Depends

from backend.app.orchestrator.runtime import build_pipeline
from backend.app.schemas.messages import ChatRequest, ChatResponse
from backend.app.security.auth import require_token
from backend.app.security.rate_limit import enforce_http_rate_limit

router = APIRouter(tags=["chat"])
pipeline = build_pipeline()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    _token: str = Depends(require_token),
    _rate_limit: None = Depends(enforce_http_rate_limit),
) -> ChatResponse:
    result = await pipeline.run_text_turn(payload.text)
    return ChatResponse(reply=result.response_text, provider="pipeline")
