from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard generic API response envelope."""

    success: bool = True
    message: str = "Operation successful"
    data: T | None = None
