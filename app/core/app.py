from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from core.config import settings
from core.exceptions import register_exception_handler
from core.lifespan import lifespan
from infrastructure.database.session import engine
from modules.auth import auth_router
from modules.chat import chat_router
from modules.collections import collections_router
from modules.documents import documents_router
from modules.processing import processing_router
from shared.schemas import ApiResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )

    register_exception_handler(app)

    # Mount static files directory for local storage provider fallback
    if settings.STORAGE_PROVIDER == "local":
        upload_dir = Path(settings.STORAGE_PATH)
        upload_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    # Mount routes
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(collections_router, prefix="/collections", tags=["Collections"])
    app.include_router(documents_router, prefix="/documents", tags=["Documents"])
    app.include_router(processing_router, prefix="/documents", tags=["AI Processing & Vector Search"])
    app.include_router(chat_router, prefix="/documents", tags=["RAG & Document Chat"])

    @app.get("/health", response_model=ApiResponse[dict], tags=["System"])
    async def health_check():
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return ApiResponse(
            message="Health check passed",
            data={"database": "connected"},
        )

    return app
