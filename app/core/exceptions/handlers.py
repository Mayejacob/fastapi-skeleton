from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
import traceback
from sqlalchemy.exc import IntegrityError, NoResultFound
from jinja2 import TemplateNotFound
from fastapi_mail.errors import ConnectionErrors
from app.core.responses import send_error
from app.utils.logging import get_logger


def register_exception_handlers(app):
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
                message="An unexpected error occurred.",
                data={"detail": str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger = get_logger()
        raw_errors = exc.errors()
        logger.warning(
            f"Validation error for {request.method} {request.url}: {raw_errors}"
        )

        friendly_errors = {}
        for error in raw_errors:
            field = ".".join(map(str, error["loc"]))
            if field.startswith("body."):
                field = field.replace("body.", "")
            friendly_errors[field] = error["msg"]

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=send_error(
                message="Validation failed",
                data={"errors": friendly_errors},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ).model_dump(),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        logger = get_logger()
        detail = str(exc.orig) if hasattr(exc, "orig") else "Database integrity error"
        logger.error(f"Integrity error for {request.method} {request.url}: {detail}")

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=send_error(
                message=detail,
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(NoResultFound)
    async def not_found_exception_handler(request: Request, exc: NoResultFound):
        logger = get_logger()
        logger.warning(f"Resource not found for {request.method} {request.url}")

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=send_error(
                message="Resource not found",
                data=None,
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

    @app.exception_handler(TemplateNotFound)
    async def template_not_found_handler(request: Request, exc: TemplateNotFound):
        logger = get_logger()
        logger.error(
            f"Template not found: '{exc.name}' while processing {request.method} {request.url}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=send_error(
                message="Email template missing or misconfigured.",
                data={
                    "template": exc.name,
                    "hint": "Ensure the template file exists in the correct folder.",
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ).model_dump(),
        )

    @app.exception_handler(ConnectionErrors)
    async def mail_connection_error_handler(request: Request, exc: ConnectionErrors):
        logger = get_logger()
        logger.error(
            f"Mail connection error for {request.method} {request.url}: {str(exc)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=send_error(
                message="Email service unavailable.",
                data={"detail": str(exc)},
                status_code=status.HTTP_502_BAD_GATEWAY,
            ).model_dump(),
        )
