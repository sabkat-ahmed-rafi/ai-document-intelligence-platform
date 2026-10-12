from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .base import AppException


def register_exception_handler(app: FastAPI): 
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exception: AppException):
        return JSONResponse(
            status_code = exception.status_code,
            content = {
                "message": exception.message,
                "code": exception.error_code
            }
        )
    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exception: Exception):
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "Something went wrong"
            }
        )