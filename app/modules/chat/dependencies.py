from fastapi import Depends

from infrastructure.database import get_db
from infrastructure.llm import get_llm
from modules.documents.dependencies import get_document_repository
from modules.documents.repository import DocumentRepository
from modules.processing.dependencies import get_chunk_repository
from modules.processing.embeddings.factory import EmbeddingFactory
from modules.processing.repository import DocumentChunkRepository

from .retriever import RAGRetriever
from .service import ChatService


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
) -> ChatService:
    """Provides a fully initialized ChatService with active LLM and retriever."""
    llm = get_llm()
    return ChatService(retriever=retriever, llm=llm)
