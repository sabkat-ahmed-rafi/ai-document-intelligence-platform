from fastapi import FastAPI
from sqlalchemy import text

from core.config import settings
from core.exceptions import register_exception_handler
from core.lifespan import lifespan
from infrastructure.database.session import engine


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )

    register_exception_handler(app)

    @app.get("/health")
    async def health_check():
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}

    return app