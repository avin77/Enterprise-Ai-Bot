from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status

from backend.app.api.chat import router as chat_router
from backend.app.schemas.messages import WsClientMessage, WsServerMessage
from backend.app.security.auth import validate_websocket_token
from backend.app.security.rate_limit import limiter

app = FastAPI(title="Enterprise AI Voice Bot", version="0.1.0")
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    try:
        token = await validate_websocket_token(websocket)
        limiter.check(f"/ws:{token}")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await websocket.send_json(WsServerMessage(type="ack", text="connected").model_dump())
    try:
        while True:
            raw = await websocket.receive_json()
            incoming = WsClientMessage.model_validate(raw)
            if incoming.type == "text" and incoming.text:
                await websocket.send_json(
                    WsServerMessage(type="bot_text", text=f"echo: {incoming.text}").model_dump()
                )
            elif incoming.type == "end":
                await websocket.send_json(WsServerMessage(type="ack", text="closed").model_dump())
                await websocket.close()
                break
    except WebSocketDisconnect:
        return

