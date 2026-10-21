from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from .dependencies import get_document_service
from .schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from .service import DocumentService

router = APIRouter()


@router.post(
    "/upload",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile = File(..., description="Document or image file to upload (max 50MB)"),
    title: str | None = Form(None, description="Optional custom document title"),
    current_user: Users = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    Accepts a document or image file, securely stores it in Amazon S3,
    records its initial state as 'pending', and immediately returns a 202 Accepted response.
    """
    result = await document_service.upload_document(
        file=file,
        user_id=current_user.id,
        title=title,
    )
    return ApiResponse(
        message="Document accepted for processing",
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
    """Retrieves document processing status, metadata, and presigned download URL."""
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
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Lists all active documents belonging to the authenticated user."""
    result = await document_service.list_documents(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        message="Documents retrieved successfully",
        data=result,
    )
