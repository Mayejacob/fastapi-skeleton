from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_early_logging
from app.core.middlewares import LogRequestsMiddleware
from app.core.openapi import custom_openapi
from app.core.rate_limiting import setup_rate_limiting

setup_early_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.PROJECT_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Auth", "description": "Authentication endpoints"},
        {"name": "Email", "description": "Email management endpoints"},
    ],
)

app.openapi = lambda: custom_openapi(app)

# Rate limiting (limiter attached to app.state; enabled flag controls enforcement)
setup_rate_limiting(app)

# Compress responses larger than 1 KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Reject requests with unexpected Host headers (production hardening)
# Set ALLOWED_HOSTS in .env to restrict (e.g. "yourdomain.com,www.yourdomain.com")
if settings.ALLOWED_HOSTS != "*":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LogRequestsMiddleware)

register_exception_handlers(app)

app.include_router(v1_router)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "frontend/home.html",
        {"request": request, "app_name": settings.APP_NAME},
    )


@app.get("/health")
async def health_check():
    from app.core.responses import send_success
    from app.db.session import engine
    from sqlalchemy import text

    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return send_success(
        message="OK",
        data={
            "status": "healthy" if db_status == "healthy" else "degraded",
            "version": settings.PROJECT_VERSION,
            "database": db_status,
        },
    )


@app.get("/test-report", response_class=HTMLResponse)
async def get_test_report(request: Request):
    import os

    report_path = os.path.join("templates", "reports", "test_report.html")

    if not os.path.exists(report_path):
        return JSONResponse(
            {
                "success": False,
                "message": "Test report not found. Run pytest to generate it.",
            },
            status_code=404,
        )

    return templates.TemplateResponse("reports/test_report.html", {"request": request})
