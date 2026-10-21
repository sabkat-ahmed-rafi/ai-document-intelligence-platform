import logging
from typing import Any
from storage3 import AsyncStorageClient
from storage3.exceptions import StorageApiError, StorageException

from .base import StorageProvider
from .exceptions import StorageConfigurationError, StorageFileNotFound, UploadFailed

logger = logging.getLogger(__name__)


class SupabaseStorageProvider(StorageProvider):
    """Supabase Storage Provider using async storage3 client."""

    def __init__(
        self,
        *,
        url: str,
        key: str,
        bucket_name: str = "documents",
        signed_url_expire_seconds: int = 3600,
        is_public: bool = False,
    ):
        if not url or not key:
            raise StorageConfigurationError(
                "SUPABASE_URL and SUPABASE_KEY are required for Supabase Storage. "
                "Please configure them in your .env file."
            )

        self.raw_url = url.rstrip("/")
        # Storage API endpoint is at /storage/v1
        self.storage_url = f"{self.raw_url}/storage/v1"
        self.key = key
        self.bucket = bucket_name
        self.signed_url_expire = signed_url_expire_seconds
        self.is_public = is_public
        self._bucket_ensured = False

        headers = {
            "apiKey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

        try:
            self._client = AsyncStorageClient(self.storage_url, headers)
            self._bucket_proxy = self._client.from_(self.bucket)
        except Exception as exc:
            logger.error("Failed to initialize Supabase storage client: %s", exc)
            raise StorageConfigurationError(f"Failed to initialize Supabase storage client: {exc}") from exc

    async def _ensure_bucket(self) -> None:
        """Ensures the storage bucket exists in Supabase. Creates it automatically if missing."""
        if self._bucket_ensured:
            return

        try:
            await self._client.get_bucket(self.bucket)
            self._bucket_ensured = True
        except StorageApiError:
            try:
                logger.info("Bucket '%s' not found. Creating bucket in Supabase Storage...", self.bucket)
                await self._client.create_bucket(
                    id=self.bucket,
                    name=self.bucket,
                    options={"public": self.is_public},
                )
                self._bucket_ensured = True
                logger.info("Bucket '%s' created successfully in Supabase Storage.", self.bucket)
            except Exception as create_exc:
                logger.warning("Could not automatically create bucket '%s': %s", self.bucket, create_exc)
                # Mark as ensured so we don't spam get_bucket on every call
                self._bucket_ensured = True
        except Exception:
            self._bucket_ensured = True

    async def upload(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str,
    ) -> str:
        await self._ensure_bucket()
        storage_path = path.lstrip("/")

        file_options: dict[str, Any] = {
            "content-type": content_type,
            "upsert": "true",
        }

        try:
            await self._bucket_proxy.upload(
                path=storage_path,
                file=content,
                file_options=file_options,
            )
            return storage_path
        except (StorageApiError, StorageException) as exc:
            logger.error("Supabase Storage upload failed for '%s': %s", storage_path, exc)
            raise UploadFailed(f"Failed to upload file to Supabase Storage: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during Supabase Storage upload for '%s': %s", storage_path, exc)
            raise UploadFailed(f"Unexpected error uploading to Supabase Storage: {exc}") from exc

    async def delete(self, key: str) -> None:
        storage_path = key.lstrip("/")
        try:
            await self._bucket_proxy.remove([storage_path])
        except Exception as exc:
            logger.error("Supabase Storage delete failed for '%s': %s", storage_path, exc)
            raise UploadFailed(f"Failed to delete file from Supabase Storage: {exc}") from exc

    async def exists(self, key: str) -> bool:
        storage_path = key.lstrip("/")
        try:
            return await self._bucket_proxy.exists(storage_path)
        except Exception as exc:
            logger.error("Supabase Storage exists check failed for '%s': %s", storage_path, exc)
            return False

    async def read(self, key: str) -> bytes:
        storage_path = key.lstrip("/")
        try:
            content = await self._bucket_proxy.download(storage_path)
            return content
        except StorageApiError as exc:
            logger.error("Supabase Storage file not found or download error: %s", exc)
            raise StorageFileNotFound(f"File '{key}' not found in Supabase bucket '{self.bucket}'") from exc
        except Exception as exc:
            logger.error("Supabase Storage read failed for '%s': %s", storage_path, exc)
            raise UploadFailed(f"Failed to read file from Supabase Storage: {exc}") from exc

    def get_url(self, key: str) -> str:
        """Returns direct URL for the file in Supabase Storage."""
        storage_path = key.lstrip("/")
        if self.is_public:
            return f"{self.storage_url}/object/public/{self.bucket}/{storage_path}"
        return f"{self.storage_url}/object/authenticated/{self.bucket}/{storage_path}"

    async def get_signed_url(self, key: str, expires_in: int | None = None) -> str:
        """Generates a secure, time-limited signed URL for private bucket access."""
        storage_path = key.lstrip("/")
        duration = expires_in or self.signed_url_expire
        try:
            res = await self._bucket_proxy.create_signed_url(
                path=storage_path,
                expires_in=duration,
            )
            raw_signed = res.get("signedURL") or res.get("signedUrl")
            if not raw_signed:
                return self.get_url(key)
            if raw_signed.startswith("http"):
                return raw_signed
            return f"{self.storage_url}{raw_signed}"
        except Exception as exc:
            logger.error("Failed to generate signed URL for '%s': %s", storage_path, exc)
            return self.get_url(key)
