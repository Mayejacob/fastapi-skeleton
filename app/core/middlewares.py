from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.utils.logging import get_logger


class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger = get_logger()
        logger.info(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        return response
