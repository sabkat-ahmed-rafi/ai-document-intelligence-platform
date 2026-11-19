from fastapi import APIRouter, Depends

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from ..dependencies import get_processing_service
from ..schemas import DocumentSummaryResponse
from ..service import ProcessingService

router = APIRouter()


@router.get(
    "/{document_id}/summary",
    response_model=ApiResponse[DocumentSummaryResponse],
    summary="Get automated executive summary and extracted entities for a document",
)
async def get_document_summary(
    document_id: str,
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Retrieves the executive summary and extracted entity catalog (parties, dates,
    financial values, classification, topics) stored in the document's metadata.
    """
    result = await processing_service.get_document_summary(
        document_id=document_id,
        user_id=current_user.id,
    )
    message = (
        "Document summary retrieved successfully"
        if result.has_summary
        else "No summary available for this document"
    )
    return ApiResponse(
        message=message,
        data=result,
    )


@router.post(
    "/{document_id}/summarize",
    response_model=ApiResponse[DocumentSummaryResponse],
    summary="Generate or re-generate document summary and entities on-demand",
)
async def summarize_document(
    document_id: str,
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Triggers on-demand executive summarization and entity extraction across all parsed chunks
    of this document, persisting the resulting summary to the document metadata.
    """
    result = await processing_service.summarize_document(
        document_id=document_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Document summary generated successfully",
        data=result,
    )
