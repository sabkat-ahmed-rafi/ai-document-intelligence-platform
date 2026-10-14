from core.exceptions import ConflictException


class EmailAlreadyExists(ConflictException):
    def __init__(self, message: str = "Email already exists"):
        super().__init__(message=message)
