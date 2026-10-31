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
