from .codes import ErrorCode

class AppException(Exception):
    status_code = 500
    message = "Internal server error"
    error_code = ErrorCode.INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, error_code: str | None = None, status_code: int | None = None):
        super().__init__(message) # In Python, the built-in Exception class expects one argument. if we don't do this then parent Exception class NEVER receives the message!

        self.message = message or self.message
        self.error_code = error_code or self.error_code
        self.status_code = status_code or self.status_code

class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message = message,
            error_code = ErrorCode.NOT_FOUND,
            status_code = 404
        )

class ValidationException(AppException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(
            message = message,
            error_code = ErrorCode.VALIDATION_ERROR,
            status_code = 422,
        )

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message = message,
            error_code = ErrorCode.UNAUTHORIZED,
            status_code = 401
        )

class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message = message,
            error_code = ErrorCode.FORBIDDEN,
            status_code = 403
        )

class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message = message,
            error_code = ErrorCode.CONFLICT,
            status_code = 409
        )