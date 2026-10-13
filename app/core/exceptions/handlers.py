import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .base import AppException
from .codes import ErrorCode

logger = logging.getLogger(__name__)


def register_exception_handler(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exception: AppException):
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "success": False,
                "message": exception.message,
                "code": exception.error_code,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exception: Exception):
        logger.exception("Unhandled server exception: %s", exception)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Something went wrong",
                "code": ErrorCode.INTERNAL_SERVER_ERROR,
            },
        )