from datetime import datetime
from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .models import File


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    url: str
    mime_type: str
    size: int
    created_at: datetime

    @classmethod
    def from_model(cls, file: "File", url: str) -> "FileResponse":
        return cls(
            id=file.id,
            original_name=file.original_name,
            url=url,
            mime_type=file.mime_type,
            size=file.size,
            created_at=file.created_at,
        )