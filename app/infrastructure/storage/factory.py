from core.config import settings
from .base import StorageProvider
from .exceptions import StorageConfigurationError
from .local import LocalStorageProvider
from .supabase import SupabaseStorageProvider


def get_storage() -> StorageProvider:
    provider = settings.STORAGE_PROVIDER.lower()

    if provider in ("supabase", "supabase_storage"):
        if not settings.SUPABASE_KEY:
            raise StorageConfigurationError(
                "Supabase Storage is selected, but SUPABASE_KEY is not set in settings or .env. "
                "Provide your Supabase Service Role Key (or Anon Key) from your Supabase dashboard."
            )
        return SupabaseStorageProvider(
            url=settings.SUPABASE_URL,
            key=settings.SUPABASE_KEY,
            bucket_name=settings.SUPABASE_STORAGE_BUCKET,
            signed_url_expire_seconds=settings.SUPABASE_SIGNED_URL_EXPIRE_SECONDS,
            is_public=settings.SUPABASE_BUCKET_PUBLIC,
        )

    if provider == "local":
        return LocalStorageProvider(settings.STORAGE_PATH)

    raise StorageConfigurationError(
        f"Unknown storage provider: '{provider}'. Supported: 'supabase', 'local'"
    )
