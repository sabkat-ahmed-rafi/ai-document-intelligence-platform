import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from infrastructure.database.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify database connection on startup
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to Supabase PostgreSQL database.")
    except Exception as exc:
        logger.error("Failed to connect to Supabase PostgreSQL database: %s", exc)
        raise

    yield

    # Clean up connection pool on shutdown
    await engine.dispose()
    logger.info("Database connection engine disposed.")
