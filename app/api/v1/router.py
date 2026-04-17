from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.email import router as email_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(email_router)
