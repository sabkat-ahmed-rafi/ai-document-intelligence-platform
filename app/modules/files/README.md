# File Management System

This module handles all file operations (upload, retrieve, delete) for the entire application. It does **not** have its own API endpoint. Instead, other modules (users, products, orders, etc.) use `FileService` internally whenever they need to handle files.

---

## Table of Contents

- [What It Can Do](#what-it-can-do)
- [Architecture Overview](#architecture-overview)
- [Folder Structure](#folder-structure)
- [How It Works](#how-it-works)
- [How to Use in a Module](#how-to-use-in-a-module)
- [How to Add a New File Category](#how-to-add-a-new-file-category)
- [How to Add Validation for a New Category](#how-to-add-validation-for-a-new-category)
- [How to Add a New Owner Type](#how-to-add-a-new-owner-type)
- [How to Add a New Storage Provider](#how-to-add-a-new-storage-provider)
- [File Storage Path Format](#file-storage-path-format)
- [Configuration](#configuration)
- [Available Exceptions](#available-exceptions)

---

## What It Can Do

| Method                  | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| `upload()`              | Validates, stores the file, and saves metadata to the DB |
| `get(file_id)`          | Retrieves a file record from DB by its ID                |
| `get_url(file)`         | Returns the public URL for a file                        |
| `delete(file_id)`       | Soft-deletes the file (marks as DELETED + removes from storage) |

---

## Architecture Overview

```
Other Modules (users, products, orders)
        │
        ▼
   FileService  ←── uses ──►  StorageProvider (abstract)
        │                           │
        ▼                     ┌─────┴──────┐
  FileRepository              │            │
        │                   Local       S3 / Cloudinary
        ▼                  (current)     (future)
    Database
```

**Key idea**: `FileService` talks to `StorageProvider` (an abstract class). It does NOT know whether files are saved on local disk, S3, or Cloudinary. To add a new storage, you just create a new class that implements `StorageProvider` — nothing in `FileService` or any other module changes.

---

## Folder Structure

```
app/
├── infrastructure/
│   └── storage/
│       ├── base.py           # StorageProvider abstract class
│       ├── local.py          # LocalStorageProvider (current implementation)
│       ├── factory.py        # get_storage() — picks the right provider from config
│       ├── types.py          # StoredFile dataclass
│       ├── exceptions.py     # StorageError, FileNotFound, UploadFailed
│       └── __init__.py
│
└── modules/
    └── files/
        ├── models.py         # File SQLAlchemy model (DB table)
        ├── service.py        # FileService — the main class other modules use
        ├── repository.py     # FileRepository — DB operations (create, get, update, delete)
        ├── dependencies.py   # FastAPI dependency injection (get_file_service)
        ├── validators.py     # FileValidator — validates file type & size per category
        ├── naming.py         # FileNamer — generates unique filenames (UUID-based)
        ├── paths.py          # FilePath — generates storage paths
        ├── enums.py          # FileCategory, OwnerType, FileStatus
        ├── schemas.py        # FileResponse pydantic model (for API responses)
        ├── exceptions.py     # FileNotFound, InvalidFileType, FileTooLarge
        └── __init__.py
```

---

## How It Works

1. Another module calls `file_service.upload(file=..., owner_type=..., owner_id=..., category=...)`
2. `FileValidator` checks if the file type and size are allowed for that category
3. `FileNamer` generates a unique filename (UUID + original extension)
4. `FilePath` builds the storage path: `{owner_type}/{owner_id}/{category}/{filename}`
5. `StorageProvider` stores the file bytes on disk (or S3, etc.)
6. `FileRepository` saves the file metadata to the database
7. The `File` model record is returned to the calling module

---

## How to Use in a Module

This is a step-by-step guide for using the file system in a **new module** (e.g., a `products` module).

### Step 1: Import FileService in your module's dependencies

```python
# app/modules/products/dependencies.py

from fastapi import Depends
from modules.files.dependencies import get_file_service
from modules.files.service import FileService

from .repository import ProductRepository
from .service import ProductService


def get_product_service(
    product_repo: ProductRepository = Depends(get_product_repository),
    file_service: FileService = Depends(get_file_service),
):

    return ProductService(
        repository=product_repo,
        file_service=file_service,
    )
```

### Step 2: Use FileService in your module's service

```python
# app/modules/products/service.py

from fastapi import UploadFile

from modules.files.service import FileService
from modules.files.enums import OwnerType, FileCategory

from .repository import ProductRepository


class ProductService:

    def __init__(
        self,
        repository: ProductRepository,
        file_service: FileService,
    ):

        self.repository = repository
        self.file_service = file_service


    async def create_product(self, data, image: UploadFile):

        product = ...  # save product to DB first

        # Upload the product image
        if image:
            file_record = await self.file_service.upload(
                file=image,
                owner_type=OwnerType.PRODUCT,
                owner_id=product.id,
                category=FileCategory.PRODUCT_IMAGE,
            )

            # file_record.id     → file ID in the database
            # file_record.size   → file size in bytes

        return product


    async def get_product_image_url(self, file_id: str):

        file = await self.file_service.get(file_id)

        url = self.file_service.get_url(file)

        return url


    async def delete_product_image(self, file_id: str):

        await self.file_service.delete(file_id)
```

### Step 3: Accept file in your API route

```python
# app/modules/products/api/router.py

from fastapi import APIRouter, UploadFile, File, Depends

from modules.products.service import ProductService
from modules.products.dependencies import get_product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/")
async def create_product(
    image: UploadFile = File(...),
    service: ProductService = Depends(get_product_service),
):

    product = await service.create_product(
        data=...,
        image=image,
    )

    return product
```

---

## How to Add a New File Category

**Example**: You want to add a `DOCUMENT` category for PDF uploads.

### Files to change: 1

**`app/modules/files/enums.py`** — Add the new category:

```diff
 class FileCategory(str, Enum):

     AVATAR = "avatar"

     PRODUCT_IMAGE = "product_image"

     INVOICE = "invoice"

     ATTACHMENT = "attachment"
+
+    DOCUMENT = "document"
```

That's it. The upload will work because categories that are NOT in `IMAGE_CATEGORIES` skip image validation (no restriction by default). If you want to add specific validation for documents, see the next section.

---

## How to Add Validation for a New Category

**Example**: You want to validate that `DOCUMENT` files are only PDFs and max 10MB.

### Files to change: 1

**`app/modules/files/validators.py`** — Add the new validation:

```diff
 from .enums import FileCategory
 from .exceptions import (
     InvalidFileType,
     FileTooLarge
 )


 IMAGE_TYPES = [
     "image/png",
     "image/jpeg",
     "image/webp"
 ]

 MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

 IMAGE_CATEGORIES = {
     FileCategory.AVATAR,
     FileCategory.PRODUCT_IMAGE,
 }

+DOCUMENT_TYPES = [
+    "application/pdf",
+]
+
+MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
+
+DOCUMENT_CATEGORIES = {
+    FileCategory.DOCUMENT,
+}
+

 class FileValidator:

     def validate(
         self,
         *,
         content_type: str,
         size: int,
         category: FileCategory,
     ):

         if category in IMAGE_CATEGORIES:
             self._validate_image(content_type, size)

+        if category in DOCUMENT_CATEGORIES:
+            self._validate_document(content_type, size)


     def _validate_image(
         self,
         content_type: str,
         size: int,
     ):

         if content_type not in IMAGE_TYPES:
             raise InvalidFileType()

         if size > MAX_IMAGE_SIZE:
             raise FileTooLarge()

+    def _validate_document(
+        self,
+        content_type: str,
+        size: int,
+    ):
+
+        if content_type not in DOCUMENT_TYPES:
+            raise InvalidFileType()
+
+        if size > MAX_DOCUMENT_SIZE:
+            raise FileTooLarge()
```

---

## How to Add a New Owner Type

**Example**: You want to add a `STORE` owner type.

### Files to change: 1

**`app/modules/files/enums.py`** — Add the new owner type:

```diff
 class OwnerType(str, Enum):

     USER = "user"

     PRODUCT = "product"

     ORDER = "order"
+
+    STORE = "store"
```

That's it. Storage paths will automatically be generated as `store/{store_id}/{category}/{filename}`.

---

## How to Add a New Storage Provider

**Example**: You want to add AWS S3 as a storage option.

### Files to change/add: 3

### 1. Create the provider class

**`app/infrastructure/storage/s3.py`** (new file) — Implement all 5 methods from `StorageProvider`:

```python
# app/infrastructure/storage/s3.py

from .base import StorageProvider
from .exceptions import FileNotFound, UploadFailed


class S3StorageProvider(StorageProvider):

    def __init__(self, bucket_name: str, region: str):
        self.bucket_name = bucket_name
        self.region = region
        # Initialize your S3 client here


    async def upload(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str,
    ) -> str:
        # Upload to S3 and return the storage key
        ...


    async def delete(self, key: str) -> None:
        # Delete from S3
        ...


    async def exists(self, key: str) -> bool:
        # Check if file exists in S3
        ...


    async def read(self, key: str) -> bytes:
        # Read file from S3
        ...


    def get_url(self, key: str) -> str:
        # Return the S3 URL
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
```

### 2. Register it in the factory

**`app/infrastructure/storage/factory.py`** — Add an `elif` for the new provider:

```diff
 from core.config import settings
 from .base import StorageProvider
 from .local import LocalStorageProvider
+from .s3 import S3StorageProvider


 def get_storage() -> StorageProvider:

     provider = settings.STORAGE_PROVIDER

     if provider == "local":
         return LocalStorageProvider(settings.STORAGE_PATH)

+    if provider == "s3":
+        return S3StorageProvider(
+            bucket_name=settings.S3_BUCKET_NAME,
+            region=settings.S3_REGION,
+        )
+
     raise ValueError(f"Unknown storage provider: {provider}")
```

### 3. Add config settings

**`app/core/config.py`** — Add the new settings:

```diff
 class Settings(BaseSettings):
     DATABASE_URL: str

     STORAGE_PROVIDER: str = "local"
     STORAGE_PATH: str = "./uploads"

+    S3_BUCKET_NAME: str = ""
+    S3_REGION: str = ""
```

**`.env`** — Switch to S3:

```env
STORAGE_PROVIDER=s3
S3_BUCKET_NAME=my-app-files
S3_REGION=ap-southeast-1
```

### What does NOT change

- `FileService` — no changes
- `FileRepository` — no changes
- `validators.py` — no changes
- `naming.py` — no changes
- `paths.py` — no changes
- `dependencies.py` — no changes
- Any module using `FileService` — no changes

---

## File Storage Path Format

Files are stored with this path structure:

```
{owner_type}/{owner_id}/{category}/{uuid_filename}
```

**Examples:**

| Owner Type | Owner ID | Category        | Generated Path                                        |
| ---------- | -------- | --------------- | ----------------------------------------------------- |
| user       | abc123   | avatar          | `user/abc123/avatar/550e8400-e29b-41d4-a716.png`      |
| product    | prod456  | product_image   | `product/prod456/product_image/6fa459ea-ee8a-3ca4.jpg` |
| order      | ord789   | invoice         | `order/ord789/invoice/f47ac10b-58cc-4372.pdf`          |

For local storage, these paths are relative to the `STORAGE_PATH` directory (default: `./uploads`).

---

## Configuration

These settings are in `app/core/config.py` and read from `.env`:

| Setting            | Default      | Description                              |
| ------------------ | ------------ | ---------------------------------------- |
| `STORAGE_PROVIDER` | `"local"`    | Which storage backend to use             |
| `STORAGE_PATH`     | `"./uploads"` | Root directory for local file storage    |

---

## Available Exceptions

### File module exceptions (`app/modules/files/exceptions.py`)

| Exception         | When it's raised                                    |
| ----------------- | --------------------------------------------------- |
| `FileNotFound`    | `get()` or `delete()` called with a non-existent ID |
| `InvalidFileType` | File mime type is not allowed for that category      |
| `FileTooLarge`    | File size exceeds the limit for that category        |

### Storage exceptions (`app/infrastructure/storage/exceptions.py`)

| Exception      | When it's raised                      |
| -------------- | ------------------------------------- |
| `StorageError` | Base exception for all storage errors |
| `FileNotFound` | Storage provider can't find the file  |
| `UploadFailed` | Storage provider failed to save       |

---

## FileService Methods Reference

### `upload()`

```python
file_record = await file_service.upload(
    file=upload_file,          # FastAPI UploadFile object
    owner_type=OwnerType.USER, # Who owns this file
    owner_id="user_123",       # ID of the owner
    category=FileCategory.AVATAR,  # What type of file
)

# Returns: File model instance with all metadata
# file_record.id           → unique file ID
# file_record.original_name → original filename
# file_record.storage_key  → internal storage path
# file_record.mime_type    → e.g. "image/png"
# file_record.size         → size in bytes
# file_record.created_at   → when it was uploaded
```

### `get()`

```python
file = await file_service.get("file_id_here")

# Returns: File model instance
# Raises: FileNotFound if ID doesn't exist
```

### `get_url()`

```python
file = await file_service.get("file_id_here")

url = file_service.get_url(file)

# Returns: URL string like "/uploads/user/123/avatar/abc.png"
# Note: Takes a File object, not a file ID
```

### `delete()`

```python
await file_service.delete("file_id_here")

# Soft-deletes: sets status to DELETED and removes from storage
# Raises: FileNotFound if ID doesn't exist
```

---

## Quick Reference — What to Change for Each Task

| Task                         | Files to Change                                                   |
| ---------------------------- | ----------------------------------------------------------------- |
| Use file system in a new module | Your module's `dependencies.py` + `service.py` + `api/router.py` |
| Add a new file category      | `enums.py` (add to `FileCategory`)                               |
| Add validation for a category | `validators.py` (add types, size limit, and validation method)   |
| Add a new owner type         | `enums.py` (add to `OwnerType`)                                  |
| Add a new storage provider   | Create new provider file + `factory.py` + `config.py` + `.env`   |
| Change file size limits      | `validators.py` (edit `MAX_IMAGE_SIZE` or add new constants)      |
| Change allowed file types    | `validators.py` (edit `IMAGE_TYPES` or add new type lists)        |
