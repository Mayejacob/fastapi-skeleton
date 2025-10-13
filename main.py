from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_early_logging
from app.core.middlewares import LogRequestsMiddleware  # Updated import
from app.core.openapi import custom_openapi
from app.core.rate_limiting import setup_rate_limiting
from fastapi.responses import HTMLResponse, JSONResponse

# Setup early logging for startup errors
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

# Customize OpenAPI schema
app.openapi = lambda: custom_openapi(app)  # Updated to lambda for app access

# Setup rate limiting if enabled
setup_rate_limiting(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LogRequestsMiddleware)  # Updated to class

# Register all exception handlers
register_exception_handlers(app)

# Include API routers
app.include_router(v1_router)

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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

    return send_success(
        message="OK", data={"status": "healthy", "version": settings.PROJECT_VERSION}
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
