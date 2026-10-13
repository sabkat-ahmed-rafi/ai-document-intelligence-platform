from abc import ABC, abstractmethod


class StorageProvider(ABC):
    @abstractmethod
    async def upload(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Store a file and return its storage key."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:
        ...

    @abstractmethod
    def get_url(self, key: str) -> str:
        ...