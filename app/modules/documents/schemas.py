from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    filename: str
    mime_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    id: str
    user_id: str
    file_id: str
    title: str
    original_filename: str
    mime_type: str
    file_size: int
    status: str
    error_message: str | None = None
    doc_metadata: dict | None = None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: list[DocumentDetailResponse]
    total: int
