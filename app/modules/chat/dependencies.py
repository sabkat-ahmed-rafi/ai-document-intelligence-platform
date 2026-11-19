from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from infrastructure.llm import get_llm
from modules.documents.dependencies import get_document_repository
from modules.documents.repository import DocumentRepository
from modules.processing.dependencies import get_chunk_repository
from modules.processing.embeddings.factory import EmbeddingFactory
from modules.processing.repository import DocumentChunkRepository

from .repository import ChatMessageRepository, ChatThreadRepository
from .retriever import RAGRetriever
from .service import ChatService
from .thread_service import ThreadService


def get_thread_repository(
    session: AsyncSession = Depends(get_db),
) -> ChatThreadRepository:
    """Provides an active ChatThreadRepository."""
    return ChatThreadRepository(session=session)


def get_message_repository(
    session: AsyncSession = Depends(get_db),
) -> ChatMessageRepository:
    """Provides an active ChatMessageRepository."""
    return ChatMessageRepository(session=session)


def get_thread_service(
    thread_repo: ChatThreadRepository = Depends(get_thread_repository),
    msg_repo: ChatMessageRepository = Depends(get_message_repository),
) -> ThreadService:
    """Provides a dedicated ThreadService for thread & message CRUD operations."""
    return ThreadService(thread_repository=thread_repo, message_repository=msg_repo)


def get_rag_retriever(
    chunk_repository: DocumentChunkRepository = Depends(get_chunk_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> RAGRetriever:
    """Provides a configured RAGRetriever with active database repositories and embedding engine."""
    embeddings = EmbeddingFactory.get_embeddings()
    return RAGRetriever(
        chunk_repository=chunk_repository,
        document_repository=document_repository,
        embeddings=embeddings,
    )


def get_chat_service(
    retriever: RAGRetriever = Depends(get_rag_retriever),
    thread_repo: ChatThreadRepository = Depends(get_thread_repository),
    msg_repo: ChatMessageRepository = Depends(get_message_repository),
) -> ChatService:
    """Provides a fully initialized ChatService with active LLM, retriever, and thread repositories."""
    llm = get_llm()
    return ChatService(
        retriever=retriever,
        llm=llm,
        thread_repo=thread_repo,
        msg_repo=msg_repo,
    )
