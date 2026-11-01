from .context import RAGContextBuilder
from .dependencies import (
    get_chat_service,
    get_message_repository,
    get_rag_retriever,
    get_thread_repository,
)
from .models import ChatMessage, ChatThread
from .prompts import (
    FALLBACK_NO_CONTEXT_ANSWER,
    RAG_HUMAN_PROMPT,
    RAG_SYSTEM_PROMPT,
    get_contextualize_q_prompt_template,
    get_conversational_rag_prompt_template,
    get_rag_prompt_template,
)
from .repository import ChatMessageRepository, ChatThreadRepository
from .retriever import RAGRetriever
from .router import router as chat_router, threads_router
from .schemas import (
    ChatMessageResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    CitationSource,
    RAGContext,
    SingleDocumentChatRequest,
    ThreadChatRequest,
    ThreadChatResponse,
    ThreadCreateRequest,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from .service import ChatService

__all__ = [
    # Routers
    "chat_router",
    "threads_router",
    # Models
    "ChatThread",
    "ChatMessage",
    # Repositories
    "ChatThreadRepository",
    "ChatMessageRepository",
    # Schemas
    "CitationSource",
    "RAGContext",
    "ChatQueryRequest",
    "SingleDocumentChatRequest",
    "ChatQueryResponse",
    "ThreadCreateRequest",
    "ThreadUpdateRequest",
    "ThreadResponse",
    "ThreadListResponse",
    "ThreadDetailResponse",
    "ChatMessageResponse",
    "ThreadChatRequest",
    "ThreadChatResponse",
    # Builders & Retrievers
    "RAGContextBuilder",
    "RAGRetriever",
    # Services
    "ChatService",
    # Dependencies
    "get_rag_retriever",
    "get_chat_service",
    "get_thread_repository",
    "get_message_repository",
    # Prompts
    "RAG_SYSTEM_PROMPT",
    "RAG_HUMAN_PROMPT",
    "FALLBACK_NO_CONTEXT_ANSWER",
    "get_rag_prompt_template",
    "get_contextualize_q_prompt_template",
    "get_conversational_rag_prompt_template",
]
