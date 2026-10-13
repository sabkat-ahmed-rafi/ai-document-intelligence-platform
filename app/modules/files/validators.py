from .enums import FileCategory
from .exceptions import InvalidFileType, FileTooLarge

ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/webp",
]

MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB


class FileValidator:
    def validate(
        self,
        *,
        content_type: str,
        size: int,
        category: FileCategory,
    ) -> None:
        if category == FileCategory.DOCUMENT:
            self._validate_document(content_type, size)

    def _validate_document(self, content_type: str, size: int) -> None:
        if content_type not in ALLOWED_DOCUMENT_TYPES:
            raise InvalidFileType(
                f"Invalid document type '{content_type}'. Allowed types: {', '.join(ALLOWED_DOCUMENT_TYPES)}"
            )

        if size > MAX_DOCUMENT_SIZE:
            raise FileTooLarge(
                f"Document size ({size} bytes) exceeds maximum limit of {MAX_DOCUMENT_SIZE // (1024 * 1024)}MB"
            )