# File Management System

This module handles all file operations (validation, storage, metadata persistence, retrieval, deletion) for the AI Document Intelligence Platform. It does **not** expose its own public API routes. Instead, other business modules (e.g. `documents`, `users`) use `FileService` internally whenever they need to process or store files.

---

## Table of Contents

- [What It Can Do](#what-it-can-do)
- [Architecture Overview](#architecture-overview)
- [Folder Structure](#folder-structure)
- [How It Works](#how-it-works)
- [How to Use in Another Module (e.g., Documents)](#how-to-use-in-another-module-eg-documents)
- [Reading File Bytes for AI / OCR Pipelines](#reading-file-bytes-for-ai--ocr-pipelines)
- [File Storage Path Format](#file-storage-path-format)
- [Configuration](#configuration)
- [Available Exceptions](#available-exceptions)
- [FileService Methods Reference](#fileservice-methods-reference)
- [How to Add a Cloud Storage Provider (e.g. Supabase Storage / S3)](#how-to-add-a-cloud-storage-provider-eg-supabase-storage--s3)

---

## What It Can Do

| Method | Description |
| :--- | :--- |
| `upload(...)` | Validates file type & size, saves bytes to storage, and persists metadata to Supabase DB |
| `get(file_id)` | Retrieves the `File` model from DB by its ID |
| `get_url(file)` | Returns the public accessible URL for the file |
| `to_response(file)` | Converts `File` DB model into a `FileResponse` Pydantic DTO (including public URL) |
| `delete(file_id)` | Soft-deletes the file (sets status to `DELETED` in DB and unlinks from storage) |
| `storage.read(storage_key)` | Reads raw `bytes` from storage (essential for AI text extraction, OCR, and embeddings) |

---

## Architecture Overview

```text
Other Modules (e.g., documents, users)
        │
        ▼
   FileService  ─── uses ───►  StorageProvider (abstract interface)
        │                                  │
        ▼                          ┌───────┴───────┐
  FileRepository                   │               │
        │                        Local      Supabase / S3
        ▼                      (current)       (future)
    Database (PostgreSQL / Supabase)
```

**Key principle**: `FileService` depends solely on the abstract `StorageProvider` interface. It does not care whether files reside on a local volume, Supabase Storage, or AWS S3. Switching storage providers requires only changing configuration or adding an implementation class — zero code changes in `FileService` or business modules.

---

## Folder Structure

```text
app/
├── infrastructure/
│   └── storage/
│       ├── base.py           # StorageProvider abstract base class
│       ├── local.py          # LocalStorageProvider implementation
│       ├── factory.py        # get_storage() factory picking provider from config
│       ├── exceptions.py     # StorageFileNotFound, UploadFailed
│       └── __init__.py
│
└── modules/
    └── files/
        ├── models.py         # File SQLAlchemy model (maps to 'files' table)
        ├── service.py        # FileService — main service used by other modules
        ├── repository.py     # FileRepository — async database operations
        ├── dependencies.py   # FastAPI dependency injection (get_file_service)
        ├── validators.py     # FileValidator — validates MIME types and size limits
        ├── naming.py         # FileNamer — generates unique UUID filenames
        ├── paths.py          # FilePath — constructs structured storage paths
        ├── enums.py          # FileCategory, OwnerType, FileStatus
        ├── schemas.py        # FileResponse Pydantic DTO
        ├── exceptions.py     # FileNotFound, InvalidFileType, FileTooLarge
        ├── README.md
        └── __init__.py
```

---

## How It Works

1. Another module calls:
   ```python
   await file_service.upload(
       file=upload_file,
       owner_type=OwnerType.DOCUMENT,
       owner_id="doc_123",
       category=FileCategory.DOCUMENT,
   )
   ```
2. `FileService` reads file content to obtain actual byte size and content type.
3. `FileValidator` verifies the MIME type is supported (e.g. PDF, Word, TXT, CSV, images) and within the 50MB limit.
4. `FileNamer` generates a unique UUID filename (preserving original extension).
5. `FilePath` constructs the storage path: `{owner_type}/{owner_id}/{category}/{filename}`.
6. `StorageProvider` writes the raw bytes to storage (e.g. `./uploads/` or cloud bucket).
7. `FileRepository` inserts the `File` metadata record into the Supabase PostgreSQL database.
8. The persisted `File` SQLAlchemy instance is returned.

---

## How to Use in Another Module (e.g., Documents)

### Step 1: Link Your Model to `files.id`

```python
# app/modules/documents/models.py
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database import Base, TimestampMixin

class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), nullable=False)
```

### Step 2: Inject `FileService` in Your Route

```python
# app/modules/documents/router.py
import uuid
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from shared.schemas import ApiResponse
from modules.files import FileService, get_file_service, FileCategory, OwnerType
from .models import Document

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=ApiResponse[dict])
async def upload_document(
    title: str,
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    db: AsyncSession = Depends(get_db),
):
    document_id = str(uuid.uuid4())

    # 1. Store physical file & save file record in database
    file_record = await file_service.upload(
        file=file,
        owner_type=OwnerType.DOCUMENT,
        owner_id=document_id,
        category=FileCategory.DOCUMENT,
    )

    # 2. Persist your document referencing the file
    doc = Document(
        id=document_id,
        title=title,
        file_id=file_record.id,
    )
    db.add(doc)
    await db.commit()

    return ApiResponse(
        message="Document uploaded successfully",
        data={
            "document_id": doc.id,
            "file": file_service.to_response(file_record).model_dump(),
        },
    )
```

---

## Reading File Bytes for AI / OCR Pipelines

When downstream AI services (e.g. LangChain, LlamaIndex, PyMuPDF, OCR models) need to extract text or embeddings:

```python
# 1. Fetch file record from database
file_record = await file_service.get(document.file_id)

# 2. Read bytes directly from storage provider
raw_bytes: bytes = await file_service.storage.read(file_record.storage_key)

# 3. Process raw bytes with your parser
extracted_text = await ocr_pipeline.extract_text(raw_bytes)
```

---

## File Storage Path Format

Files are saved following this path layout:

```text
{owner_type}/{owner_id}/{category}/{uuid_filename}
```

**Examples:**

| Owner Type | Owner ID | Category | Generated Storage Key |
| :--- | :--- | :--- | :--- |
| `document` | `doc_123` | `document` | `document/doc_123/document/550e8400-e29b-41d4-a716-446655440000.pdf` |
| `user` | `usr_456` | `document` | `user/usr_456/document/6fa459ea-ee8a-3ca4-b521-884812349000.docx` |

For local storage, paths are relative to `STORAGE_PATH` (default: `./uploads`).

---

## Configuration

Settings are declared in [`app/core/config.py`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/core/config.py) and read from `.env`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `STORAGE_PROVIDER` | `"local"` | Storage driver (`"local"`, or future `"supabase"` / `"s3"`) |
| `STORAGE_PATH` | `"./uploads"` | Base directory for local file storage |

---

## Available Exceptions

### Files Module Exceptions ([`app/modules/files/exceptions.py`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/modules/files/exceptions.py))

| Exception | HTTP Status | When Raised |
| :--- | :--- | :--- |
| `FileNotFound` | 404 | `get()` or `delete()` called with non-existent file ID |
| `InvalidFileType` | 422 | File MIME type not in allowed document types list |
| `FileTooLarge` | 422 | File size exceeds 50MB limit |

### Storage Exceptions ([`app/infrastructure/storage/exceptions.py`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/infrastructure/storage/exceptions.py))

| Exception | HTTP Status | When Raised |
| :--- | :--- | :--- |
| `StorageFileNotFound` | 404 | Storage provider cannot find file on disk / bucket |
| `UploadFailed` | 500 | Storage provider encountered I/O write error |

---

## FileService Methods Reference

### `upload()`
```python
file_record = await file_service.upload(
    file=upload_file,              # FastAPI UploadFile object
    owner_type=OwnerType.DOCUMENT, # Who/what owns this file
    owner_id="doc_123",            # Owner identifier
    category=FileCategory.DOCUMENT,# File category
)
# Returns: File SQLAlchemy model
```

### `get()`
```python
file_record = await file_service.get(file_id)
# Returns: File SQLAlchemy model (raises FileNotFound if missing)
```

### `get_url()`
```python
url = file_service.get_url(file_record)
# Returns: "/uploads/document/doc_123/document/<uuid>.pdf"
```

### `to_response()`
```python
response_dto = file_service.to_response(file_record)
# Returns: FileResponse schema with id, original_name, url, mime_type, size, created_at
```

### `delete()`
```python
await file_service.delete(file_id)
# Unlinks physical file from storage and marks status as DELETED in database
```

---

## How to Add a Cloud Storage Provider (e.g. Supabase Storage / S3)

To add a new storage driver:

1. Create a new provider class implementing `StorageProvider`:
   ```python
   # app/infrastructure/storage/supabase.py
   from .base import StorageProvider

   class SupabaseStorageProvider(StorageProvider):
       async def upload(self, *, path: str, content: bytes, content_type: str) -> str:
           ...
       async def delete(self, key: str) -> None:
           ...
       async def exists(self, key: str) -> bool:
           ...
       async def read(self, key: str) -> bytes:
           ...
       def get_url(self, key: str) -> str:
           ...
   ```
2. Update [`app/infrastructure/storage/factory.py`](file:///D:/Code/Projects/ai-document-intelligence-platform/app/infrastructure/storage/factory.py):
   ```python
   if provider == "supabase":
       return SupabaseStorageProvider(...)
   ```
3. Update `STORAGE_PROVIDER=supabase` in `.env`. Zero changes needed in `FileService` or business modules.
