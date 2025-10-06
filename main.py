from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.db.session import init_db
from app.utils.caching import cache
from app.utils.logging import get_logger

app = FastAPI(title="FastAPI Skeleton")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    logger = get_logger()
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    return response


app.include_router(v1_router)


@app.on_event("startup")
async def startup_event():
    await init_db()
    await cache.init_redis()


@app.on_event("shutdown")
async def shutdown_event():
    await cache.close()


@app.get("/")
async def root():
    from app.core.responses import send_success

    return send_success(message="Welcome to FastAPI Skeleton").model_dump()
