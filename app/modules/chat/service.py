from datetime import datetime, timezone
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from core.config import settings
from core.exceptions import AppException, NotFoundException, ValidationException
from infrastructure.llm.exceptions import LLMGenerationError

from .models import ChatMessage, ChatThread
from .prompts import (
    FALLBACK_NO_CONTEXT_ANSWER,
    get_contextualize_q_prompt_template,
    get_conversational_rag_prompt_template,
    get_rag_prompt_template,
)
from .repository import ChatMessageRepository, ChatThreadRepository
from .retriever import RAGRetriever
from .schemas import (
    ChatMessageResponse,
    ChatQueryResponse,
    ThreadChatResponse,
)


class ChatService:
    """
    RAG Orchestration & Conversational Memory Service.
    Coordinates:
    1. Single-turn RAG question-answering over documents with inline citations.
    2. Multi-turn conversational chat threads with message persistence.
    3. Contextual query reformulation using chat history.
    4. Conversational RAG synthesis incorporating prior conversation turns.
    5. Real-time token streaming via Server-Sent Events (SSE).
    """

    def __init__(
        self,
        retriever: RAGRetriever,
        llm: BaseChatModel,
        thread_repo: ChatThreadRepository | None = None,
        msg_repo: ChatMessageRepository | None = None,
        prompt_template: ChatPromptTemplate | None = None,
        output_parser: StrOutputParser | None = None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.thread_repo = thread_repo
        self.msg_repo = msg_repo
        self.prompt_template = prompt_template or get_rag_prompt_template()
        self.output_parser = output_parser or StrOutputParser()

        # 1. Single-turn LCEL chain
        self.chain = self.prompt_template | self.llm | self.output_parser

        # 2. Conversational query contextualization chain (reformulates follow-ups into standalone queries)
        self.contextualize_chain = (
            get_contextualize_q_prompt_template() | self.llm | self.output_parser
        )

        # 3. Multi-turn conversational RAG chain (grounded QA with conversation history)
        self.conversational_chain = (
            get_conversational_rag_prompt_template() | self.llm | self.output_parser
        )

    def _resolve_model_metadata(self) -> tuple[str, str]:
        """Resolves active model name and provider string for observability."""
        model_name = (
            getattr(self.llm, "model_name", None)
            or getattr(self.llm, "model", None)
            or settings.LLM_MODEL
        )
        provider = settings.LLM_PROVIDER.strip().lower()
        return str(model_name), provider

    # =========================================================================
    # Single-Turn RAG (Stateless)
    # =========================================================================

    async def query(
        self,
        *,
        user_id: str,
        question: str,
        search_mode: str = "hybrid",
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> ChatQueryResponse:
        """
        Executes single-turn RAG question answering:
        1. Retrieves top-k semantically relevant chunks.
        2. Fast-exits if context is empty (zero token cost).
        3. Invokes LLM via LCEL pipeline.
        4. Returns grounded answer with structured citation metadata.
        """
        start_time = time.perf_counter()
        clean_question = question.strip()
        model_name, provider = self._resolve_model_metadata()

        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=clean_question,
            search_mode=search_mode,
            collection_id=collection_id,
            document_id=document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

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
        search_mode: str = "hybrid",
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streams single-turn RAG answer token-by-token for real-time frontend rendering.
        """
        start_time = time.perf_counter()
        clean_question = question.strip()
        model_name, provider = self._resolve_model_metadata()

        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=clean_question,
            search_mode=search_mode,
            collection_id=collection_id,
            document_id=document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        yield {
            "event": "metadata",
            "data": {
                "question": clean_question,
                "citations": [c.model_dump() for c in rag_context.citations],
                "model": model_name,
                "provider": provider,
            },
        }

        if rag_context.is_empty:
            yield {"event": "token", "data": {"token": FALLBACK_NO_CONTEXT_ANSWER}}
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            yield {
                "event": "done",
                "data": {"execution_time_ms": execution_time_ms},
            }
            return

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

    # =========================================================================
    # Thread Management CRUD
    # =========================================================================

    async def create_thread(
        self,
        *,
        user_id: str,
        title: str = "New Conversation",
        collection_id: str | None = None,
        document_id: str | None = None,
    ) -> ChatThread:
        if not self.thread_repo:
            raise AppException("ChatThreadRepository is not configured")

        clean_title = title.strip() if title else "New Conversation"
        now = datetime.now(timezone.utc)
        thread = ChatThread(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=clean_title,
            collection_id=collection_id,
            document_id=document_id,
            created_at=now,
            updated_at=now,
        )
        return await self.thread_repo.create(thread)

    async def get_thread(
        self,
        thread_id: str,
        user_id: str,
        include_messages: bool = True,
    ) -> ChatThread:
        if not self.thread_repo:
            raise AppException("ChatThreadRepository is not configured")

        thread = await self.thread_repo.get_by_id(
            thread_id=thread_id,
            user_id=user_id,
            include_messages=include_messages,
        )
        if not thread:
            raise NotFoundException(f"Chat thread '{thread_id}' not found")
        return thread

    async def list_threads(
        self,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[ChatThread, int]], int]:
        if not self.thread_repo:
            raise AppException("ChatThreadRepository is not configured")

        return await self.thread_repo.list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def update_thread_title(
        self,
        *,
        thread_id: str,
        user_id: str,
        title: str,
    ) -> ChatThread:
        clean_title = title.strip()
        if not clean_title:
            raise ValidationException("Thread title cannot be empty")

        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        thread.title = clean_title
        return await self.thread_repo.update(thread)

    async def delete_thread(
        self,
        *,
        thread_id: str,
        user_id: str,
    ) -> None:
        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        await self.thread_repo.soft_delete(thread)

    async def list_thread_messages(
        self,
        *,
        thread_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[ChatMessage], int]:
        if not self.msg_repo:
            raise AppException("ChatMessageRepository is not configured")

        # Verify thread access
        await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        return await self.msg_repo.list_for_thread(
            thread_id=thread_id,
            limit=limit,
            offset=offset,
        )

    # =========================================================================
    # Multi-Turn Conversational Memory & RAG Execution
    # =========================================================================

    async def thread_query(
        self,
        *,
        thread_id: str,
        user_id: str,
        message: str,
        search_mode: str = "hybrid",
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> ThreadChatResponse:
        """
        Executes a multi-turn conversational turn within a thread:
        1. Loads recent conversation history.
        2. Contextualizes the follow-up question into a standalone query.
        3. Retrieves relevant chunks scoped to user, thread collection/document.
        4. Synthesizes answer using conversation history and grounded excerpts.
        5. Persists user and assistant messages with citations and metrics.
        """
        if not self.thread_repo or not self.msg_repo:
            raise AppException("Thread repositories are not configured")

        start_time = time.perf_counter()
        clean_message = message.strip()
        if not clean_message:
            raise ValidationException("Message cannot be empty")

        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        model_name, provider = self._resolve_model_metadata()

        # 1. Fetch recent history (last 10 messages)
        history_records = await self.msg_repo.get_recent_history(thread_id=thread.id, limit=10)
        history_messages = []
        for h in history_records:
            if h.role == "user":
                history_messages.append(HumanMessage(content=h.content))
            elif h.role == "assistant":
                history_messages.append(AIMessage(content=h.content))

        # 2. Contextualize query if prior turns exist
        standalone_query = clean_message
        if history_messages:
            try:
                condensed = await self.contextualize_chain.ainvoke(
                    {
                        "chat_history": history_messages,
                        "question": clean_message,
                    }
                )
                condensed_clean = str(condensed).strip()
                if condensed_clean:
                    standalone_query = condensed_clean
            except Exception:
                standalone_query = clean_message

        # 3. Retrieve context chunks scoped to thread knowledge base
        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=standalone_query,
            search_mode=search_mode,
            collection_id=thread.collection_id,
            document_id=thread.document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # 4. Synthesize answer
        if rag_context.is_empty:
            answer_text = FALLBACK_NO_CONTEXT_ANSWER
        else:
            try:
                answer_val = await self.conversational_chain.ainvoke(
                    {
                        "context": rag_context.formatted_context,
                        "question": clean_message,
                        "chat_history": history_messages,
                    }
                )
                answer_text = str(answer_val).strip()
            except Exception as exc:
                raise LLMGenerationError(f"Conversational synthesis failed: {exc}") from exc

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        now = datetime.now(timezone.utc)

        # 5. Persist user message
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="user",
            content=clean_message,
            created_at=now,
        )
        user_saved = await self.msg_repo.create(user_msg)

        # 6. Persist assistant message
        citations_data = (
            [c.model_dump() for c in rag_context.citations] if rag_context.citations else None
        )
        assistant_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="assistant",
            content=answer_text,
            citations=citations_data,
            model=model_name,
            provider=provider,
            execution_time_ms=execution_time_ms,
            created_at=now,
        )
        assistant_saved = await self.msg_repo.create(assistant_msg)

        # 7. Update thread timestamp
        await self.thread_repo.update(thread)

        return ThreadChatResponse(
            user_message=ChatMessageResponse.model_validate(user_saved),
            assistant_message=ChatMessageResponse.model_validate(assistant_saved),
            standalone_query=standalone_query if standalone_query != clean_message else None,
        )

    async def stream_thread_query(
        self,
        *,
        thread_id: str,
        user_id: str,
        message: str,
        search_mode: str = "hybrid",
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streams multi-turn conversational answer token-by-token via SSE:
        - Reformulates follow-up queries with chat history.
        - Persists user message upfront.
        - Yields 'metadata' event with citations and standalone query.
        - Streams 'token' events in real time.
        - Persists completed assistant message and yields 'done' event.
        """
        if not self.thread_repo or not self.msg_repo:
            raise AppException("Thread repositories are not configured")

        start_time = time.perf_counter()
        clean_message = message.strip()
        if not clean_message:
            yield {"event": "error", "data": {"error": "Message cannot be empty"}}
            return

        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        model_name, provider = self._resolve_model_metadata()

        # 1. Fetch recent history
        history_records = await self.msg_repo.get_recent_history(thread_id=thread.id, limit=10)
        history_messages = []
        for h in history_records:
            if h.role == "user":
                history_messages.append(HumanMessage(content=h.content))
            elif h.role == "assistant":
                history_messages.append(AIMessage(content=h.content))

        # 2. Contextualize query if prior turns exist
        standalone_query = clean_message
        if history_messages:
            try:
                condensed = await self.contextualize_chain.ainvoke(
                    {
                        "chat_history": history_messages,
                        "question": clean_message,
                    }
                )
                condensed_clean = str(condensed).strip()
                if condensed_clean:
                    standalone_query = condensed_clean
            except Exception:
                standalone_query = clean_message

        # 3. Retrieve context chunks scoped to thread knowledge base
        rag_context = await self.retriever.retrieve(
            user_id=user_id,
            query=standalone_query,
            search_mode=search_mode,
            collection_id=thread.collection_id,
            document_id=thread.document_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # 4. Persist user message upfront
        now = datetime.now(timezone.utc)
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="user",
            content=clean_message,
            created_at=now,
        )
        user_saved = await self.msg_repo.create(user_msg)

        # 5. Emit metadata event
        yield {
            "event": "metadata",
            "data": {
                "thread_id": thread.id,
                "user_message_id": user_saved.id,
                "question": clean_message,
                "standalone_query": standalone_query if standalone_query != clean_message else None,
                "citations": [c.model_dump() for c in rag_context.citations],
                "model": model_name,
                "provider": provider,
            },
        }

        # 6. If no context, emit fallback token directly
        if rag_context.is_empty:
            yield {"event": "token", "data": {"token": FALLBACK_NO_CONTEXT_ANSWER}}
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            assistant_msg = ChatMessage(
                id=str(uuid.uuid4()),
                thread_id=thread.id,
                role="assistant",
                content=FALLBACK_NO_CONTEXT_ANSWER,
                citations=None,
                model=model_name,
                provider=provider,
                execution_time_ms=execution_time_ms,
                created_at=datetime.now(timezone.utc),
            )
            assistant_saved = await self.msg_repo.create(assistant_msg)
            await self.thread_repo.update(thread)
            yield {
                "event": "done",
                "data": {
                    "assistant_message_id": assistant_saved.id,
                    "execution_time_ms": execution_time_ms,
                },
            }
            return

        # 7. Stream tokens via conversational chain
        full_tokens: list[str] = []
        try:
            async for token_chunk in self.conversational_chain.astream(
                {
                    "context": rag_context.formatted_context,
                    "question": clean_message,
                    "chat_history": history_messages,
                }
            ):
                if token_chunk:
                    text_chunk = str(token_chunk)
                    full_tokens.append(text_chunk)
                    yield {"event": "token", "data": {"token": text_chunk}}
        except Exception as exc:
            yield {"event": "error", "data": {"error": f"Stream generation failed: {exc}"}}
            return

        full_answer = "".join(full_tokens).strip()
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 8. Persist assistant message with citations and timing
        citations_data = (
            [c.model_dump() for c in rag_context.citations] if rag_context.citations else None
        )
        assistant_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="assistant",
            content=full_answer,
            citations=citations_data,
            model=model_name,
            provider=provider,
            execution_time_ms=execution_time_ms,
            created_at=datetime.now(timezone.utc),
        )
        assistant_saved = await self.msg_repo.create(assistant_msg)
        await self.thread_repo.update(thread)

        yield {
            "event": "done",
            "data": {
                "assistant_message_id": assistant_saved.id,
                "execution_time_ms": execution_time_ms,
            },
        }
