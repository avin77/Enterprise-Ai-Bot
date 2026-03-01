import os
from typing import Annotated

from fastapi import Header, HTTPException, Request, WebSocket, status


def _expected_token() -> str:
    return os.getenv("API_TOKEN", "dev-token")


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _is_valid_token(token: str | None) -> bool:
    return bool(token) and token == _expected_token()


async def require_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    token = _extract_bearer(authorization)
    if not _is_valid_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing token",
        )
    request.state.auth_token = token
    return token


async def validate_websocket_token(websocket: WebSocket) -> str:
    token = websocket.query_params.get("token")
    if token is None:
        token = _extract_bearer(websocket.headers.get("authorization"))
    if not _is_valid_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing token",
        )
    return token

