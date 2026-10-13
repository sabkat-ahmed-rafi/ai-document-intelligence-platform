from core.exceptions import NotFoundException, ValidationException


class InvalidFileType(ValidationException):
    def __init__(self, message: str = "Invalid file type"):
        super().__init__(message=message)


class FileTooLarge(ValidationException):
    def __init__(self, message: str = "File too large"):
        super().__init__(message=message)


class FileNotFound(NotFoundException):
    def __init__(self, message: str = "File not found"):
        super().__init__(message=message)
