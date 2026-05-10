from fastapi.openapi.utils import get_openapi
from app.core.config import settings


def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.PROJECT_VERSION,
        description="API documentation with Bearer token authentication",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }

    # Apply Bearer auth globally — all endpoints require a token by default
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Endpoints marked with openapi_extra={"security": []} in the router
    # already carry security=[] in their schema — no further patching needed.
    # The loop below ensures any endpoint that explicitly sets security=[]
    # is not overridden by the global default.
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("security") == []:
                # Already marked as public — keep it
                pass

    app.openapi_schema = openapi_schema
    return app.openapi_schema
