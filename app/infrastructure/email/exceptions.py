from core.exceptions import AppException, ErrorCode


class EmailConfigurationError(AppException):
    def __init__(self, message: str = "Email service is not configured"):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=500,
        )


class EmailDeliveryFailed(AppException):
    def __init__(self, message: str = "Email delivery failed"):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=502,
        )


class EmailTemplateError(AppException):
    def __init__(self, message: str = "Email template could not be rendered"):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=500,
        )
