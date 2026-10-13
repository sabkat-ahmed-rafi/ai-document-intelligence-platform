from fastapi import FastAPI

from core.exceptions import register_exception_handler


def create_app() -> FastAPI:

    app = FastAPI()

    register_exception_handler(app)


    return app