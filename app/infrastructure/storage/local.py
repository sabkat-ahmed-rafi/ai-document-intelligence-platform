from pathlib import Path

import anyio

from .base import StorageProvider
from .exceptions import StorageFileNotFound, UploadFailed


class LocalStorageProvider(StorageProvider):

    def __init__(self, storage_path: str):
        self.root = Path(storage_path)


    async def upload(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str,
    ) -> str:

        full_path = self.root / path

        def _write():
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(content)

        try:
            await anyio.to_thread.run_sync(_write)
        except OSError as e:
            raise UploadFailed(str(e))

        return path


    async def delete(self, key: str) -> None:

        full_path = self.root / key

        def _delete():
            if full_path.exists():
                full_path.unlink()

        await anyio.to_thread.run_sync(_delete)


    async def exists(self, key: str) -> bool:

        full_path = self.root / key

        return await anyio.to_thread.run_sync(full_path.exists)


    async def read(self, key: str) -> bytes:

        full_path = self.root / key

        def _read():
            if not full_path.exists():
                raise StorageFileNotFound(f"File not found: {key}")
            return full_path.read_bytes()

        return await anyio.to_thread.run_sync(_read)


    def get_url(self, key: str) -> str:

        return f"/uploads/{key}"
