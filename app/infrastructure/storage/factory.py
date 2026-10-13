from core.config import settings
from .base import StorageProvider
from .local import LocalStorageProvider


def get_storage() -> StorageProvider:

    provider = settings.STORAGE_PROVIDER

    if provider == "local":
        return LocalStorageProvider(settings.STORAGE_PATH)

    raise ValueError(f"Unknown storage provider: {provider}")