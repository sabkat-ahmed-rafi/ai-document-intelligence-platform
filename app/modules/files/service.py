import uuid
from fastapi import UploadFile

from core.config import settings
from infrastructure.storage import StorageProvider

from .enums import FileCategory, FileStatus, OwnerType
from .exceptions import FileNotFound
from .models import File
from .naming import FileNamer
from .paths import FilePath
from .repository import FileRepository
from .schemas import FileResponse
from .validators import FileValidator


class FileService:

    def __init__(
        self,
        repository: FileRepository,
        storage: StorageProvider,
        validator: FileValidator,
        namer: FileNamer,
        path_generator: FilePath,
    ):
        self.repository = repository
        self.storage = storage
        self.validator = validator
        self.namer = namer
        self.path_generator = path_generator

    async def upload(
        self,
        *,
        file: UploadFile,
        owner_type: OwnerType,
        owner_id: str,
        category: FileCategory,
        content: bytes | None = None,
        resolved_content_type: str | None = None,
    ) -> File:
        # Use pre-read content or read file content
        if content is None:
            content = await file.read()
        file_size = len(content)
        raw_content_type = resolved_content_type or file.content_type or "application/octet-stream"

        # Validate based on category, actual size, and filename
        content_type = self.validator.validate(
            content_type=raw_content_type,
            size=file_size,
            category=category,
            filename=file.filename,
        )

        # Safely extract extension and generate unique filename
        original_name = file.filename or "file"
        if "." in original_name:
            extension = original_name.rsplit(".", 1)[-1].lower()
        else:
            extension = "bin"

        filename = self.namer.generate(extension)

        # Build storage path
        path = self.path_generator.generate(
            owner_type=owner_type,
            owner_id=owner_id,
            category=category,
            filename=filename,
        )

        # Store the file in storage provider
        storage_key = await self.storage.upload(
            path=path,
            content=content,
            content_type=content_type,
        )

        owner_type_val = owner_type.value if hasattr(owner_type, "value") else str(owner_type)
        category_val = category.value if hasattr(category, "value") else str(category)

        # Save metadata to database
        file_record = File(
            id=str(uuid.uuid4()),
            original_name=original_name,
            storage_key=storage_key,
            provider=settings.STORAGE_PROVIDER,
            mime_type=content_type,
            size=file_size,
            owner_type=owner_type_val,
            owner_id=owner_id,
            category=category_val,
        )

        return await self.repository.create(file_record)

    async def get(self, file_id: str) -> File:
        file = await self.repository.get_by_id(file_id)

        if not file:
            raise FileNotFound()

        return file

    def get_url(self, file: File) -> str:
        return self.storage.get_url(file.storage_key)

    def to_response(self, file: File) -> FileResponse:
        """Convert a File model instance into a FileResponse schema with its public URL."""
        return FileResponse.from_model(file, url=self.get_url(file))

    async def delete(self, file_id: str) -> None:
        file = await self.get(file_id)

        await self.storage.delete(file.storage_key)

        file.status = FileStatus.DELETED.value

        await self.repository.update(file)
