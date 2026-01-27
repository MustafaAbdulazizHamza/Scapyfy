from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import os

DEFAULT_RATE = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
AUTH_RATE = os.getenv("RATE_LIMIT_AUTH", "5/minute")


def get_client_identifier(request: Request) -> str:
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_identifier)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": getattr(exc, 'retry_after', 60)
        }
    )


def auth_rate_limit():
    return limiter.limit(AUTH_RATE)


def default_rate_limit():
    return limiter.limit(DEFAULT_RATE)
