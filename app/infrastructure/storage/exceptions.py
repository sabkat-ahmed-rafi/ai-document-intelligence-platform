from core.exceptions import AppException
from core.exceptions.codes import ErrorCode
from core.exceptions import NotFoundException


class StorageFileNotFound(NotFoundException):
    def __init__(self, message: str = "File not found in storage"):
        super().__init__(message=message)


class UploadFailed(AppException, OSError):
    def __init__(self, message: str = "Upload failed"):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=500,
        )
