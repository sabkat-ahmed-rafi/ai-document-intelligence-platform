from fastapi import APIRouter

from .password_reset import router as password_reset_router
from .registration import router as registration_router
from .session import router as session_router

router = APIRouter()
router.include_router(registration_router)
router.include_router(session_router)
router.include_router(password_reset_router)
