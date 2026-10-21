from .enums import FileCategory
from .exceptions import InvalidFileType, FileTooLarge

ALLOWED_DOCUMENT_TYPES = [
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "text/markdown",
    # Images
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/tiff",
    "image/bmp",
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
        # Normalize mime type
        normalized_type = content_type.lower().split(";")[0].strip()
        if normalized_type not in ALLOWED_DOCUMENT_TYPES:
            raise InvalidFileType(
                f"Invalid file type '{content_type}'. Allowed types: PDF, Word (.docx, .doc), Text (.txt, .md, .csv), and Images (.png, .jpg, .jpeg, .webp, .tiff, .bmp)"
            )

        if size > MAX_DOCUMENT_SIZE:
            raise FileTooLarge(
                f"File size ({size} bytes) exceeds maximum limit of {MAX_DOCUMENT_SIZE // (1024 * 1024)}MB"
            )
