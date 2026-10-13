from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from infrastructure.storage import get_storage

from .repository import FileRepository
from .service import FileService
from .validators import FileValidator
from .naming import FileNamer
from .paths import FilePath


def get_file_repository(
    session: AsyncSession = Depends(get_db),
):

    return FileRepository(session)


def get_file_service(
    repository: FileRepository = Depends(get_file_repository),
    storage=Depends(get_storage),
):

    return FileService(
        repository=repository,
        storage=storage,
        validator=FileValidator(),
        namer=FileNamer(),
        path_generator=FilePath(),
    )