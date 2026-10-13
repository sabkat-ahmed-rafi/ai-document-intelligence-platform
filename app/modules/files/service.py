import uuid
from fastapi import UploadFile

from infrastructure.storage import StorageProvider
from core.config import settings

from .models import File
from .schemas import FileResponse
from .repository import FileRepository
from .validators import FileValidator
from .naming import FileNamer
from .enums import FileCategory, OwnerType, FileStatus
from .paths import FilePath
from .exceptions import FileNotFound


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
    ) -> File:
        # Read file content first so we have the guaranteed actual byte size
        content = await file.read()
        file_size = len(content)
        content_type = file.content_type or "application/octet-stream"

        # Validate based on category and actual size
        self.validator.validate(
            content_type=content_type,
            size=file_size,
            category=category,
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
