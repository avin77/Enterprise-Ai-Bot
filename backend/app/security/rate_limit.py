import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def max_requests() -> int:
        return int(os.getenv("RATE_LIMIT_REQUESTS", "30"))

    @staticmethod
    def window_seconds() -> int:
        return int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    def check(self, key: str) -> None:
        now = time.monotonic()
        max_requests = self.max_requests()
        window = self.window_seconds()
        with self._lock:
            events = self._events[key]
            while events and (now - events[0]) > window:
                events.popleft()
            if len(events) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate limit exceeded",
                )
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = InMemoryRateLimiter()


def _request_identity(request: Request) -> str:
    token = getattr(request.state, "auth_token", "unknown")
    return f"{request.url.path}:{token}"


async def enforce_http_rate_limit(request: Request) -> None:
    limiter.check(_request_identity(request))

