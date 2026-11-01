from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class CitationSource(BaseModel):
    """
    Structured metadata for a single source chunk cited by the RAG model.
    Enables frontends to render interactive citation chips, page badges, and source previews.
    """

    source_number: int = Field(
        ...,
        description="Sequential reference number corresponding to [Source N] in the answer",
    )
    document_id: str = Field(..., description="UUID of the parent document")
    document_title: str = Field(..., description="Document title or original filename")
    chunk_id: str = Field(..., description="UUID of the document chunk")
    chunk_index: int = Field(..., description="0-indexed position of chunk in the document")
    page_number: int | str | None = Field(
        None,
        description="Document page number or range where this chunk is located (if available)",
    )
    snippet: str = Field(
        ...,
        description="Truncated preview of the chunk text content for UI tooltips",
    )
    similarity: float = Field(
        ...,
        description="Cosine similarity score (0.0 to 1.0) between query and chunk",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGContext(BaseModel):
    """
    Encapsulates formatted context string ready for LLM prompt injection
    along with structured citation references.
    """

    formatted_context: str = Field(
        ...,
        description="Numbered and formatted context string injected into the LLM prompt",
    )
    citations: list[CitationSource] = Field(
        default_factory=list,
        description="List of citation references matching [Source 1], [Source 2], etc.",
    )
    total_sources: int = Field(default=0, description="Total number of chunks included in context")
    is_empty: bool = Field(default=False, description="True if no relevant chunks were found")


class ChatQueryRequest(BaseModel):
    """Payload for submitting a question to the Document Chat & RAG Engine."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question to ask over the documents",
        examples=["What were the Q4 revenue figures?", "Summarize the termination policy."],
    )
    collection_id: str | None = Field(
        None,
        description="Optional collection UUID to scope the search within a specific knowledge base",
    )
    document_id: str | None = Field(
        None,
        description="Optional document UUID to scope the search to a single document",
    )
    top_k: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of context chunks to retrieve for synthesis",
    )
    similarity_threshold: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score required for chunks to be included",
    )
    search_mode: Literal["hybrid", "vector", "keyword"] = Field(
        default="hybrid",
        description="Search algorithm: 'hybrid' (Vector + BM25 via RRF), 'vector' (cosine only), 'keyword' (BM25 only)",
    )
    stream: bool = Field(
        False,
        description="If true, stream the generated tokens in real-time via Server-Sent Events (SSE)",
    )


class SingleDocumentChatRequest(BaseModel):
    """Payload for submitting a question scoped to a specific document."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question to ask over this document",
        examples=["What is the total revenue reported on page 3?", "List key contract terms."],
    )
    top_k: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of context chunks to retrieve for synthesis",
    )
    similarity_threshold: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score required for chunks to be included",
    )
    search_mode: Literal["hybrid", "vector", "keyword"] = Field(
        default="hybrid",
        description="Search algorithm: 'hybrid' (Vector + BM25 via RRF), 'vector' (cosine only), 'keyword' (BM25 only)",
    )
    stream: bool = Field(
        False,
        description="If true, stream the generated tokens in real-time via Server-Sent Events (SSE)",
    )


class ChatQueryResponse(BaseModel):
    """Response returned by the Document Chat & RAG Engine."""

    question: str = Field(..., description="The original user question")
    answer: str = Field(..., description="Grounded, synthesized answer with inline [Source N] tags")
    citations: list[CitationSource] = Field(
        default_factory=list,
        description="Structured citations corresponding to all [Source N] tags in the answer",
    )
    model: str = Field(..., description="Active LLM model used for synthesis")
    provider: str = Field(..., description="Active LLM provider used (groq, openai, gemini, etc.)")
    execution_time_ms: float = Field(
        ...,
        description="Total roundtrip execution time in milliseconds (retrieval + synthesis)",
    )

    model_config = ConfigDict(from_attributes=True)


# =========================================================================
# Conversational Memory & Chat Threads Schemas
# =========================================================================


class ThreadCreateRequest(BaseModel):
    """Payload to create a new conversational chat thread."""

    title: str = Field(
        default="New Conversation",
        min_length=1,
        max_length=255,
        description="Human-readable title for the chat thread",
        examples=["Q3 Financial Analysis", "Vendor Contract Review"],
    )
    collection_id: str | None = Field(
        default=None,
        description="Optional collection UUID to restrict conversational retrieval to a collection",
    )
    document_id: str | None = Field(
        default=None,
        description="Optional document UUID to restrict conversational retrieval to a single document",
    )


class ThreadUpdateRequest(BaseModel):
    """Payload to rename an existing conversational thread."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Updated title for the chat thread",
        examples=["Renamed: Legal Disclaimers"],
    )


class ChatMessageResponse(BaseModel):
    """Represents a persisted message within a chat thread."""

    id: str = Field(..., description="Message UUID")
    thread_id: str = Field(..., description="Thread UUID")
    role: str = Field(..., description="Message author role ('user', 'assistant', 'system')")
    content: str = Field(..., description="The textual message content")
    citations: list[CitationSource] | None = Field(
        default=None,
        description="Source citations for assistant responses",
    )
    model: str | None = Field(default=None, description="LLM model used for generation")
    provider: str | None = Field(default=None, description="LLM provider name")
    execution_time_ms: float | None = Field(
        default=None,
        description="Execution latency in milliseconds",
    )
    created_at: datetime = Field(..., description="UTC creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ThreadResponse(BaseModel):
    """Summary of a chat thread including message count."""

    id: str = Field(..., description="Thread UUID")
    user_id: str = Field(..., description="User UUID owner")
    title: str = Field(..., description="Thread title")
    collection_id: str | None = Field(default=None, description="Scoped collection UUID")
    document_id: str | None = Field(default=None, description="Scoped document UUID")
    message_count: int = Field(default=0, description="Total active messages in this thread")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last message or update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ThreadListResponse(BaseModel):
    """Paginated list of chat threads."""

    items: list[ThreadResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total active threads count")
    limit: int = Field(..., description="Page limit")
    offset: int = Field(..., description="Page offset")


class ThreadDetailResponse(BaseModel):
    """Detailed view of a chat thread including all chronological messages."""

    id: str = Field(..., description="Thread UUID")
    user_id: str = Field(..., description="User UUID owner")
    title: str = Field(..., description="Thread title")
    collection_id: str | None = Field(default=None, description="Scoped collection UUID")
    document_id: str | None = Field(default=None, description="Scoped document UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last message or update timestamp")
    messages: list[ChatMessageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ThreadChatRequest(BaseModel):
    """Payload to submit a conversational question in a multi-turn thread."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or follow-up prompt",
        examples=["Can you elaborate on the second clause?", "Why did the profit drop?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of context chunks to retrieve for synthesis",
    )
    similarity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score required for chunks to be included",
    )
    search_mode: Literal["hybrid", "vector", "keyword"] = Field(
        default="hybrid",
        description="Search algorithm: 'hybrid' (Vector + BM25 via RRF), 'vector', or 'keyword'",
    )
    stream: bool = Field(
        default=False,
        description="If true, stream the generated tokens in real-time via Server-Sent Events (SSE)",
    )


class ThreadChatResponse(BaseModel):
    """Batch response for a multi-turn conversational turn."""

    user_message: ChatMessageResponse = Field(..., description="Persisted user question message")
    assistant_message: ChatMessageResponse = Field(
        ...,
        description="Persisted assistant answer message with citations",
    )
    standalone_query: str | None = Field(
        default=None,
        description="The reformulated standalone query generated from chat history",
    )

    model_config = ConfigDict(from_attributes=True)
