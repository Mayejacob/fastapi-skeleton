from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
)


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from app.core.responses import send_error
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=send_error(
            message=f"Too many requests. {exc.detail}",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        ).model_dump(),
    )


def setup_rate_limiting(app):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
