from fastapi import APIRouter, Depends, Query, status

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from .dependencies import get_collection_service
from .schemas import (
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from .service import CollectionService

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[CollectionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document collection",
)
async def create_collection(
    data: CollectionCreate,
    current_user: Users = Depends(get_current_active_user),
    collection_service: CollectionService = Depends(get_collection_service),
):
    """Creates a new collection (smart folder / knowledge base) to organize documents."""
    result = await collection_service.create_collection(
        data=data,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Collection created successfully",
        data=result,
    )


@router.get(
    "",
    response_model=ApiResponse[CollectionListResponse],
    summary="List all collections for current user",
)
async def list_collections(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    collection_service: CollectionService = Depends(get_collection_service),
):
    """Lists all collections owned by the user, including document counts."""
    result = await collection_service.list_collections(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        message="Collections retrieved successfully",
        data=result,
    )


@router.get(
    "/{collection_id}",
    response_model=ApiResponse[CollectionResponse],
    summary="Get collection details",
)
async def get_collection(
    collection_id: str,
    current_user: Users = Depends(get_current_active_user),
    collection_service: CollectionService = Depends(get_collection_service),
):
    """Retrieves details of a specific collection."""
    result = await collection_service.get_collection(
        collection_id=collection_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Collection retrieved successfully",
        data=result,
    )


@router.patch(
    "/{collection_id}",
    response_model=ApiResponse[CollectionResponse],
    summary="Update a collection",
)
async def update_collection(
    collection_id: str,
    data: CollectionUpdate,
    current_user: Users = Depends(get_current_active_user),
    collection_service: CollectionService = Depends(get_collection_service),
):
    """Updates collection name or description."""
    result = await collection_service.update_collection(
        collection_id=collection_id,
        user_id=current_user.id,
        data=data,
    )
    return ApiResponse(
        message="Collection updated successfully",
        data=result,
    )


@router.delete(
    "/{collection_id}",
    response_model=ApiResponse[None],
    summary="Delete a collection (cascade delete)",
)
async def delete_collection(
    collection_id: str,
    current_user: Users = Depends(get_current_active_user),
    collection_service: CollectionService = Depends(get_collection_service),
):
    """Deletes a collection and cascades deletion to all documents inside it."""
    await collection_service.delete_collection(
        collection_id=collection_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Collection and all contained documents deleted successfully",
        data=None,
    )
