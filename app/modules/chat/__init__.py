from .context import RAGContextBuilder
from .dependencies import get_chat_service, get_rag_retriever
from .prompts import (
    FALLBACK_NO_CONTEXT_ANSWER,
    RAG_HUMAN_PROMPT,
    RAG_SYSTEM_PROMPT,
    get_rag_prompt_template,
)
from .retriever import RAGRetriever
from .router import router as chat_router
from .schemas import (
    ChatQueryRequest,
    ChatQueryResponse,
    CitationSource,
    RAGContext,
    SingleDocumentChatRequest,
)
from .service import ChatService

__all__ = [
    "chat_router",
    "CitationSource",
    "RAGContext",
    "ChatQueryRequest",
    "SingleDocumentChatRequest",
    "ChatQueryResponse",
    "RAGContextBuilder",
    "RAGRetriever",
    "ChatService",
    "get_rag_retriever",
    "get_chat_service",
    "RAG_SYSTEM_PROMPT",
    "RAG_HUMAN_PROMPT",
    "FALLBACK_NO_CONTEXT_ANSWER",
    "get_rag_prompt_template",
]
