import uuid
from core.exceptions import NotFoundException, ValidationException

from .models import Collection
from .repository import CollectionRepository
from .schemas import (
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)


class CollectionService:
    def __init__(self, repository: CollectionRepository):
        self.repository = repository

    async def create_collection(
        self,
        data: CollectionCreate,
        user_id: str,
    ) -> CollectionResponse:
        existing = await self.repository.get_by_name(data.name, user_id)
        if existing:
            raise ValidationException(f"A collection named '{data.name}' already exists.")

        collection = Collection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
        )
        saved = await self.repository.create(collection)
        return CollectionResponse(
            id=saved.id,
            user_id=saved.user_id,
            name=saved.name,
            description=saved.description,
            document_count=0,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )

    async def get_or_create_by_name(
        self,
        name: str,
        user_id: str,
    ) -> Collection:
        existing = await self.repository.get_by_name(name, user_id)
        if existing:
            return existing

        collection = Collection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name.strip(),
            description=None,
        )
        return await self.repository.create(collection)

    async def get_collection(
        self,
        collection_id: str,
        user_id: str,
    ) -> CollectionResponse:
        collection = await self.repository.get_by_id(collection_id, user_id)
        if not collection:
            raise NotFoundException("Collection not found")

        doc_count = await self.repository.get_document_count(collection_id)
        return CollectionResponse(
            id=collection.id,
            user_id=collection.user_id,
            name=collection.name,
            description=collection.description,
            document_count=doc_count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    async def list_collections(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> CollectionListResponse:
        rows, total = await self.repository.list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        items = [
            CollectionResponse(
                id=col.id,
                user_id=col.user_id,
                name=col.name,
                description=col.description,
                document_count=doc_count,
                created_at=col.created_at,
                updated_at=col.updated_at,
            )
            for col, doc_count in rows
        ]
        return CollectionListResponse(collections=items, total=total)

    async def update_collection(
        self,
        collection_id: str,
        user_id: str,
        data: CollectionUpdate,
    ) -> CollectionResponse:
        collection = await self.repository.get_by_id(collection_id, user_id)
        if not collection:
            raise NotFoundException("Collection not found")

        if data.name is not None and data.name.strip():
            # Check unique name if changed
            if data.name.strip().lower() != collection.name.lower():
                existing = await self.repository.get_by_name(data.name, user_id)
                if existing and existing.id != collection_id:
                    raise ValidationException(f"A collection named '{data.name}' already exists.")
            collection.name = data.name.strip()

        if data.description is not None:
            collection.description = data.description.strip() if data.description.strip() else None

        updated = await self.repository.update(collection)
        doc_count = await self.repository.get_document_count(collection_id)
        return CollectionResponse(
            id=updated.id,
            user_id=updated.user_id,
            name=updated.name,
            description=updated.description,
            document_count=doc_count,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    async def delete_collection(
        self,
        collection_id: str,
        user_id: str,
    ) -> None:
        collection = await self.repository.get_by_id(collection_id, user_id)
        if not collection:
            raise NotFoundException("Collection not found")

        # Hard delete collection; PostgreSQL ON DELETE CASCADE will automatically delete all linked documents
        await self.repository.delete(collection)
