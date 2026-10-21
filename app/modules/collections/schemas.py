from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the collection")
    description: str | None = Field(None, max_length=1000, description="Optional description of the collection")


class CollectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)


class CollectionResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int
