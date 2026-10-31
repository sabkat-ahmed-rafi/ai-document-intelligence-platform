import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from core.config import settings
from infrastructure.llm.exceptions import LLMGenerationError
from .prompts import FALLBACK_NO_CONTEXT_ANSWER, get_rag_prompt_template
from .retriever import RAGRetriever
from .schemas import ChatQueryResponse


class ChatService:
    """
    RAG Orchestration Service.
    Coordinates context retrieval from Supabase pgvector, prompt generation via LangChain LCEL,
    anti-hallucination grounding, and response synthesis with inline [Source N] citations.
    Supports both batch execution and Server-Sent Event (SSE) token streaming.
    """

    def __init__(
        self,
        retriever: RAGRetriever,
        llm: BaseChatModel,
        prompt_template: ChatPromptTemplate | None = None,
        output_parser: StrOutputParser | None = None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.prompt_template = prompt_template or get_rag_prompt_template()
        self.output_parser = output_parser or StrOutputParser()

        # Build declarative LangChain Expression Language (LCEL) chain
        self.chain = self.prompt_template | self.llm | self.output_parser

    def _resolve_model_metadata(self) -> tuple[str, str]:
        """Resolves active model name and provider string for observability."""
        model_name = (
            getattr(self.llm, "model_name", None)
            or getattr(self.llm, "model", None)
            or settings.LLM_MODEL
        )
        provider = settings.LLM_PROVIDER.strip().lower()
        return str(model_name), provider

    async def query(
        self,
        *,
        user_id: str,
        question: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> ChatQueryResponse:
        """
        Executes end-to-end RAG question answering:
        1. Retrieves top-k semantically relevant chunks from pgvector.
        2. Bypasses LLM if context is empty (zero token cost & instantaneous response).
        3. Formats prompt with strict anti-hallucination rules and context excerpts.
        4. Invokes LLM via LangChain LCEL pipeline.
        5. Returns grounded answer with structured citation metadata.
        """
        start_time = time.perf_counter()
        clean_question = question.strip()
        model_name, provider = self._resolve_model_metadata()

        # 1. Retrieve grounded context
        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=clean_question,
            collection_id=collection_id,
            document_id=document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # 2. Fast-exit if zero relevant context exists (saves API costs & prevents hallucination)
        if rag_context.is_empty:
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ChatQueryResponse(
                question=clean_question,
                answer=FALLBACK_NO_CONTEXT_ANSWER,
                citations=[],
                model=model_name,
                provider=provider,
                execution_time_ms=execution_time_ms,
            )

        # 3. Invoke LangChain RAG chain
        try:
            answer = await self.chain.ainvoke(
                {
                    "context": rag_context.formatted_context,
                    "question": clean_question,
                }
            )
        except Exception as exc:
            raise LLMGenerationError(f"LLM synthesis failed: {exc}") from exc

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ChatQueryResponse(
            question=clean_question,
            answer=str(answer).strip(),
            citations=rag_context.citations,
            model=model_name,
            provider=provider,
            execution_time_ms=execution_time_ms,
        )

    async def stream_query(
        self,
        *,
        user_id: str,
        question: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streams RAG answer token-by-token for real-time frontend rendering:
        - Yields 'metadata' event first with structured citation sources.
        - Yields 'token' events as words are produced by the LLM.
        - Yields 'done' event with timing metrics when complete.
        """
        start_time = time.perf_counter()
        clean_question = question.strip()
        model_name, provider = self._resolve_model_metadata()

        # 1. Retrieve grounded context
        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=clean_question,
            collection_id=collection_id,
            document_id=document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # 2. Yield metadata event with citation cards immediately
        yield {
            "event": "metadata",
            "data": {
                "question": clean_question,
                "citations": [c.model_dump() for c in rag_context.citations],
                "model": model_name,
                "provider": provider,
            },
        }

        # 3. If empty, stream the fallback message directly without invoking LLM
        if rag_context.is_empty:
            yield {"event": "token", "data": {"token": FALLBACK_NO_CONTEXT_ANSWER}}
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            yield {
                "event": "done",
                "data": {"execution_time_ms": execution_time_ms},
            }
            return

        # 4. Stream tokens via LangChain LCEL astream
        try:
            async for token_chunk in self.chain.astream(
                {
                    "context": rag_context.formatted_context,
                    "question": clean_question,
                }
            ):
                if token_chunk:
                    yield {"event": "token", "data": {"token": str(token_chunk)}}
        except Exception as exc:
            yield {
                "event": "error",
                "data": {"error": f"Stream generation error: {exc}"},
            }
            return

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        yield {
            "event": "done",
            "data": {"execution_time_ms": execution_time_ms},
        }
