# 01 — Storage Architecture & Document Ingestion System

## 1. Overview & Rationale
The Document Ingestion subsystem is the entry gateway of the platform. It is engineered to accept single or high-volume multi-file uploads (PDFs, Word documents, text files, and high-resolution images), validate them strictly before touching persistent storage, stream binaries into **Supabase Cloud Storage**, register their metadata in **PostgreSQL**, and enqueue background processing via **Celery**.

---

## 2. Why `HTTP 202 Accepted`?
In standard REST design, `200 OK` or `201 Created` implies that the resource is fully created and ready for immediate consumption.

However, in an AI Document Intelligence system:
* Extracting layout from a 50-page PDF or OCR-ing high-res receipts takes **3 to 30 seconds**.
* Generating dense vector embeddings takes additional time.
* If the API waited synchronously for parsing and vector generation before responding, the HTTP request would block, browsers and load balancers would throw **`504 Gateway Timeout`**, and users would face an unusable UI.

**`HTTP 202 Accepted`** establishes an asynchronous contract:
1. The server confirms: *"Your files are valid and safely stored in cloud storage with initial status `pending`."*
2. The server provides immediate unique `document_id`s.
3. The server immediately delegates parsing, chunking, and embedding to distributed **Celery** workers.

---

## 3. Two-Phase Atomic Pre-Validation ("All-or-Nothing")

A critical production requirement is **atomicity**: if a user uploads a batch of 10 files and the 10th file is corrupt, empty, or an executable (`.exe`), **zero files should be saved to cloud storage, and zero records should be created in PostgreSQL**.

To achieve this, the pipeline enforces a **two-phase architecture**:

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / Frontend
    participant API as FastAPI Router (/documents/upload)
    participant Validator as FileValidator Engine
    participant Storage as Supabase Storage
    participant DB as PostgreSQL Database
    participant Queue as Celery / Redis Queue

    User->>API: POST /documents/upload (files=[f1, f2, f3], JWT)
    
    rect rgb(240, 248, 255)
        Note over API,Validator: Phase 1: In-Memory Atomic Pre-Validation
        loop For every file in batch
            API->>Validator: Inspect bytes, size, extension, MIME type
            alt Validation fails on ANY file
                Validator-->>API: Raise ValidationException (e.g. invalid type, empty)
                API-->>User: HTTP 400 Bad Request (0 files saved, 0 DB rows)
            end
        end
    end

    rect rgb(245, 255, 245)
        Note over API,Queue: Phase 2: Ingestion, Storage & Dispatch (All files passed)
        loop For every validated file
            API->>Storage: Stream binary to 'documents/{user_id}/uuid.ext'
            Storage-->>API: Return storage_key
            API->>DB: Insert 'files' row (physical file tracking)
            API->>DB: Insert 'documents' row (status: "pending")
            API->>Queue: Enqueue process_document_task.delay(doc_id)
        end
        API-->>User: HTTP 202 Accepted (batch summary + document_ids)
    end
```

### Validation Rules Enforced (`FileValidator`):
1. **Empty File Guard:** `size > 0` bytes. Empty files raise `FileEmpty`.
2. **Size Ceiling:** `size <= 50 MB` (enforced in `MAX_DOCUMENT_SIZE`). Larger files raise `FileTooLarge`.
3. **Extension Whitelist:** File extension must belong to:
   ```python
   ALLOWED_DOCUMENT_EXTENSIONS = {
       ".pdf", ".docx", ".doc", ".txt", ".csv", ".md",
       ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp",
   }
   ```
4. **MIME Whitelist with Fallback Guessing:**
   Browsers often send generic `application/octet-stream` for `.md` or `.csv`. The validator inspects `content_type`, and if generic, resolves the true MIME type using Python's `mimetypes.guess_type(filename)`.
5. **Atomic Rollback Safeguard:**
   If an unexpected network disruption occurs while uploading file 8 of 10 to Supabase Storage, the `try...except` block catches the error and purges the already-uploaded 7 files from Supabase Storage:
   ```python
   except Exception as exc:
       for rec in uploaded_file_records:
           await self.file_service.storage.delete(rec.storage_key)
       raise exc
   ```

---

## 4. Cloud Storage Architecture (`StorageProvider`)

The platform isolates storage interactions behind a clean abstract interface:

```
app/infrastructure/storage/
├── base.py       # StorageProvider ABC (upload, delete, exists, get_url, get_signed_url)
├── factory.py    # StorageFactory (instantiates active provider based on config)
├── supabase.py   # SupabaseStorageProvider (storage3.AsyncStorageClient)
├── s3.py         # S3StorageProvider (boto3)
└── local.py      # LocalStorageProvider (local disk fallback)
```

### Supabase Storage Provider Details:
* **Client Library:** `storage3.AsyncStorageClient` (pure asynchronous HTTP storage client).
* **Bucket Configuration:** Default bucket `documents`. The provider verifies bucket existence on startup and creates it automatically if missing:
  ```python
  await self.client.create_bucket(self.bucket_name, options={"public": False})
  ```
* **Security & Access Control:**
  * By default, `SUPABASE_BUCKET_PUBLIC = False`.
  * Files are **not accessible via public URLs**.
  * Access is granted via **time-limited signed download URLs** generated on demand using `get_signed_url(path, expires_in=3600)`.
* **Path Naming Strategy:**
  Files are namespaced by owner and category to prevent collisions and simplify multi-tenant management:
  ```
  documents/{owner_id}/{category}/{unique_uuid}.{extension}
  Example: documents/0ec9c16e-9c93/document/355ff883-df05-457b.pdf
  ```

---

## 5. Database Tracking (`files` vs `documents`)

To ensure clean separation of concerns, physical files and logical documents are split into two database models:

```
┌───────────────────────────────────────┐
│                 files                 │  <-- Physical File Layer
├───────────────────────────────────────┤
│ id: String (UUID PK)                  │
│ storage_key: String                   │  e.g. documents/user_1/doc/uuid.pdf
│ provider: String                      │  e.g. "supabase", "s3"
│ mime_type: String                     │  e.g. "application/pdf"
│ size: Integer                         │  Bytes
│ owner_type: String                    │  "document", "avatar"
│ owner_id: String                      │  User UUID
└──────────────────┬────────────────────┘
                   │ 1:1
┌──────────────────▼────────────────────┐
│               documents               │  <-- Domain / Business Layer
├───────────────────────────────────────┤
│ id: String (UUID PK)                  │
│ user_id: String (FK -> users.id)      │
│ collection_id: String (FK, Nullable)  │
│ file_id: String (FK -> files.id)      │
│ title: String                         │
│ original_filename: String             │
│ status: String                        │  "pending" -> "processing" -> "completed"
│ doc_metadata: JSONB                   │  Parser info, chunk counts, timings
└───────────────────────────────────────┘
```

---

## 6. API Specification: `POST /documents/upload`

* **Method:** `POST`
* **Content-Type:** `multipart/form-data`
* **Authentication:** Bearer JWT Access Token

### Request Parameters:
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `files` | `file[]` | Optional* | Multi-file array selection. Accepts 1 to 40+ files at once. |
| `file` | `file` | Optional* | Single file fallback. *(At least one of `files` or `file` is required)* |
| `collection_id` | `string` | Optional | UUID of an existing collection to group documents into. |
| `collection_name`| `string` | Optional | Name of collection to auto-create on the fly if `collection_id` is omitted. |
| `title` | `string` | Optional | Custom title override (applied when uploading a single document). |

### Success Response (`HTTP 202 Accepted`):
```json
{
  "success": true,
  "message": "2 documents accepted for processing into collection",
  "data": {
    "collection_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "total_uploaded": 2,
    "total_failed": 0,
    "document_id": "doc_1111",
    "uploaded": [
      {
        "document_id": "doc_1111",
        "collection_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "pending",
        "filename": "q4_report.pdf",
        "mime_type": "application/pdf",
        "file_size": 1048576,
        "created_at": "2026-10-23T00:10:00Z"
      },
      {
        "document_id": "doc_2222",
        "collection_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "pending",
        "filename": "supplier_agreement.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "file_size": 524288,
        "created_at": "2026-10-23T00:10:00Z"
      }
    ],
    "failed": []
  }
}
```

### Error Response (Validation Failure — `HTTP 400 Bad Request`):
```json
{
  "success": false,
  "message": "Batch upload rejected. 1 file(s) failed validation; no files were saved: 'malicious.exe': Unsupported file extension '.exe'. Allowed extensions: .bmp, .csv, .doc, .docx, .jpeg, .jpg, .md, .pdf, .png, .tiff, .txt, .webp",
  "data": null
}
```
*(Notice: The entire request is rejected, zero storage bytes consumed, zero database records created).*

---

### Navigation
[← Documentation Blueprint](./README.md) | [Next: 02 — Collections & Organization →](./02_collections_and_organization.md)
