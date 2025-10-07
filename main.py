from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from fastapi import Request
from app.api.v1.router import router as v1_router
from app.db.session import init_db
from app.utils.caching import cache
from app.utils.logging import get_logger
from app.core.config import settings
from app.core.responses import send_success
from slowapi import Limiter, _rate_limit_exceeded_handler  # For rate limiting
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from app.core.responses import APIResponse, send_error, send_success

# Early fallback logger for startup errors (before settings/Loguru)
os.makedirs("logs", exist_ok=True)
early_logger = logging.getLogger("startup")
early_logger.setLevel(logging.ERROR)
fh = logging.FileHandler("logs/startup.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
early_logger.addHandler(fh)
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
early_logger.addHandler(console_handler)

# Rate limiting setup (conditional)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.PROJECT_VERSION,
    debug=settings.DEBUG,  # Enables debug mode (e.g., detailed errors in dev)
)


# Conditional: Add SlowAPI middleware if enabled
if settings.RATE_LIMIT_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Example global limiter (apply to routes with @limiter.limit("5/minute"))
    # Customize per-route: e.g., @router.post("/", dependencies=[Depends(limiter.limit("5/minute"))])

# CORS with env-based origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,  # Uses parsed list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     logger = get_logger()
#     logger.info(f"Request: {request.method} {request.url}")
#     response = await call_next(request)
#     return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger()
    logger.error(
        f"Unhandled exception for {request.method} {request.url}: {exc}\n"
        f"Traceback: {traceback.format_exc()}\n"
        f"User-Agent: {request.headers.get('user-agent')}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=send_error(
            message=str(exc), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger = get_logger()
    raw_errors = exc.errors()
    logger.warning(f"Validation error for {request.method} {request.url}: {raw_errors}")

    # Transform to user-friendly dict (e.g., {"field": "error message"})
    friendly_errors = {}
    for error in raw_errors:
        field = ".".join(map(str, error["loc"]))  # e.g., "body.username" -> "username"
        if field.startswith("body."):
            field = field.replace("body.", "")  # Clean up
        friendly_errors[field] = error["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=send_error(
            message="Validation failed",
            data={"errors": friendly_errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger = get_logger()
    logger.warning(
        f"HTTP {exc.status_code} for {request.method} {request.url}: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=send_error(
            message=exc.detail, status_code=exc.status_code
        ).model_dump(),
    )


app.include_router(v1_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await cache.init_redis()
    logger = get_logger()
    logger.info(f"Startup: {settings.APP_NAME} v{settings.PROJECT_VERSION} starting...")
    yield
    # Shutdown
    await cache.close()
    logger.info("Shutdown: App shutting down...")


app.router.lifespan_context = lifespan  # Attach to app


@app.get("/")
async def root():
    from app.core.responses import send_success

    return send_success(message=f"Welcome to {settings.APP_NAME}!").model_dump()


# Example health check
@app.get("/health")
async def health_check():
    from app.core.responses import send_success

    return send_success(
        message="OK", data={"status": "healthy", "version": settings.PROJECT_VERSION}
    )
