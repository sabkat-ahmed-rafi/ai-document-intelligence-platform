from core.exceptions import AppException


class LLMConfigurationError(AppException):
    """Raised when an LLM provider is misconfigured (missing API key or invalid settings)."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=500)


class LLMGenerationError(AppException):
    """Raised when an LLM fails to generate a response (e.g., provider outage, rate limit)."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=502)
