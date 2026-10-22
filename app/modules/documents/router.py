from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)

from core.exceptions import ValidationException
from modules.auth.dependencies import get_current_active_user
from modules.processing.tasks import enqueue_document_processing
from modules.users.model import Users
from shared.schemas import ApiResponse

from .dependencies import get_document_service
from .schemas import (
    DocumentBatchUploadResponse,
    DocumentDetailResponse,
    DocumentListResponse,
)
from .service import DocumentService

router = APIRouter()


@router.post(
    "/upload",
    response_model=ApiResponse[DocumentBatchUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload one or multiple documents for processing",
)
async def upload_documents(
    files: list[UploadFile] = File(
        default=[],
        description="One or multiple document or image files to upload (max 50MB each)",
    ),
    file: UploadFile | None = File(
        default=None,
        description="Single document or image file fallback",
    ),
    title: str | None = Form(
        None,
        description="Optional custom title (applied when uploading a single document)",
    ),
    collection_id: str | None = Form(
        None,
        description="Optional UUID of an existing collection to group these documents into",
    ),
    collection_name: str | None = Form(
        None,
        description="Optional collection name (will auto-create collection if collection_id is not provided)",
    ),
    current_user: Users = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    Accepts one or multiple documents/images using tolerant batch ingestion.
    Valid files are securely uploaded to cloud storage, recorded with initial 'pending'
    status in PostgreSQL, and enqueued for background AI processing via Celery.
    Invalid or corrupted files are isolated in the 'failed' response array with exact error
    reasons, allowing partial success and single-file retry without blocking valid documents.
    Returns HTTP 202 Accepted when at least one file succeeds.
    """
    upload_list = list(files)
    if file is not None and file not in upload_list:
        upload_list.append(file)

    if not upload_list:
        raise ValidationException("At least one document or image file must be provided")

    result = await document_service.upload_documents(
        files=upload_list,
        user_id=current_user.id,
        title=title,
        collection_id=collection_id,
        collection_name=collection_name,
    )

    # Enqueue automatic distributed AI processing via Celery
    for uploaded_doc in result.uploaded:
        enqueue_document_processing(
            document_id=uploaded_doc.document_id,
            user_id=current_user.id,
        )

    count = result.total_uploaded
    msg = f"{count} document{'s' if count != 1 else ''} accepted for processing"
    if result.collection_id:
        msg += " into collection"
    if result.total_failed > 0:
        msg += f" ({result.total_failed} file{'s' if result.total_failed != 1 else ''} failed)"

    return ApiResponse(
        message=msg,
        data=result,
    )


@router.get(
    "/{document_id}",
    response_model=ApiResponse[DocumentDetailResponse],
    summary="Get document details and status",
)
async def get_document(
    document_id: str,
    current_user: Users = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Retrieves document processing status, metadata, collection_id, and presigned/signed download URL."""
    result = await document_service.get_document(
        document_id=document_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Document retrieved successfully",
        data=result,
    )


@router.get(
    "",
    response_model=ApiResponse[DocumentListResponse],
    summary="List all documents for the current user",
)
async def list_documents(
    collection_id: str | None = Query(None, description="Optional filter by collection UUID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Lists all active documents belonging to the user, optionally filtered by collection."""
    result = await document_service.list_documents(
        user_id=current_user.id,
        collection_id=collection_id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        message="Documents retrieved successfully",
        data=result,
    )
