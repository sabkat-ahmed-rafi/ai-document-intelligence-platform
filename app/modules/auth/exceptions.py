from core.exceptions import ConflictException, ForbiddenException, UnauthorizedException


class InvalidCredentials(UnauthorizedException):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message)


class TokenExpired(UnauthorizedException):
    def __init__(self, message: str = "Token expired or invalid"):
        super().__init__(message=message)


class InactiveUser(ForbiddenException):
    def __init__(self, message: str = "Inactive user account"):
        super().__init__(message=message)


class InvalidPasswordReset(UnauthorizedException):
    def __init__(self, message: str = "Invalid or expired password reset code/token"):
        super().__init__(message=message)


class InvalidCurrentPassword(UnauthorizedException):
    def __init__(self, message: str = "Current password does not match"):
        super().__init__(message=message)
