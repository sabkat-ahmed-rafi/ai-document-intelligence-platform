import mimetypes
from pathlib import Path

from .enums import FileCategory
from .exceptions import FileEmpty, FileTooLarge, InvalidFileType

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

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".csv",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tiff",
    ".bmp",
}

MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB


class FileValidator:
    def validate(
        self,
        *,
        content_type: str,
        size: int,
        category: FileCategory,
        filename: str | None = None,
    ) -> str:
        """
        Validates content_type, size, and filename.
        Returns the resolved, normalized content_type.
        """
        if category == FileCategory.DOCUMENT:
            return self._validate_document(content_type, size, filename)
        return content_type

    def _validate_document(
        self,
        content_type: str,
        size: int,
        filename: str | None = None,
    ) -> str:
        if size <= 0:
            raise FileEmpty("File cannot be empty (0 bytes received)")

        if size > MAX_DOCUMENT_SIZE:
            raise FileTooLarge(
                f"File size ({size} bytes) exceeds maximum limit of {MAX_DOCUMENT_SIZE // (1024 * 1024)}MB"
            )

        # Check file extension if filename is provided
        if filename:
            ext = Path(filename).suffix.lower()
            if ext and ext not in ALLOWED_DOCUMENT_EXTENSIONS:
                allowed_ext_str = ", ".join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))
                raise InvalidFileType(
                    f"Unsupported file extension '{ext}'. Allowed extensions: {allowed_ext_str}"
                )

        # Normalize content type
        normalized_type = content_type.lower().split(";")[0].strip() if content_type else ""

        # If generic or missing, try guessing from filename
        if (not normalized_type or normalized_type == "application/octet-stream") and filename:
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type:
                normalized_type = guessed_type.lower().split(";")[0].strip()

        if normalized_type not in ALLOWED_DOCUMENT_TYPES:
            raise InvalidFileType(
                f"Unsupported file MIME type '{content_type}'. Allowed types: PDF, Word (.docx, .doc), Text (.txt, .md, .csv), and Images (.png, .jpg, .jpeg, .webp, .tiff, .bmp)"
            )

        return normalized_type
