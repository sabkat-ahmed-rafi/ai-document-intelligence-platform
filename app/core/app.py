from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from core.config import settings
from core.exceptions import register_exception_handler
from core.lifespan import lifespan
from infrastructure.database.session import engine
from shared.schemas import ApiResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )

    register_exception_handler(app)

    # Mount static files directory for local storage provider
    if settings.STORAGE_PROVIDER == "local":
        upload_dir = Path(settings.STORAGE_PATH)
        upload_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    @app.get("/health", response_model=ApiResponse[dict])
    async def health_check():
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return ApiResponse(
            message="Health check passed",
            data={"database": "connected"},
        )

    return app