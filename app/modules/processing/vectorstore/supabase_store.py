from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings

from ..models import DocumentChunk
from ..repository import DocumentChunkRepository


class SupabaseVectorStoreAdapter:
    """
    Adapter providing standard LangChain VectorStore-compatible operations
    over Supabase PostgreSQL pgvector.
    """

    def __init__(
        self,
        repository: DocumentChunkRepository,
        embeddings: Embeddings,
    ):
        self.repository = repository
        self.embeddings = embeddings

    async def add_documents(
        self,
        documents: list[LCDocument],
        *,
        document_id: str,
        user_id: str,
        collection_id: str | None = None,
    ) -> list[DocumentChunk]:
        """
        Embeds a batch of LangChain documents and inserts them into Supabase pgvector.
        """
        if not documents:
            return []

        # 1. Extract texts
        texts = [doc.page_content for doc in documents]

        # 2. Generate embeddings in batch
        vectors = await self.embeddings.aembed_documents(texts)

        # 3. Build DocumentChunk entities
        import uuid
        chunk_models: list[DocumentChunk] = []
        for idx, (doc, vector) in enumerate(zip(documents, vectors)):
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                collection_id=collection_id,
                user_id=user_id,
                content=doc.page_content,
                chunk_index=doc.metadata.get("chunk_index", idx),
                token_count=doc.metadata.get("estimated_tokens"),
                char_count=len(doc.page_content),
                chunk_metadata=doc.metadata,
                embedding=vector,
            )
            chunk_models.append(chunk)

        # 4. Save into Supabase PostgreSQL
        return await self.repository.create_many(chunk_models)

    async def similarity_search(
        self,
        query: str,
        *,
        user_id: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        k: int = 5,
    ) -> list[tuple[LCDocument, float]]:
        """
        Performs semantic similarity search for a text query.
        Returns tuples of (LCDocument, similarity_score).
        """
        query_vector = await self.embeddings.aembed_query(query)
        results = await self.repository.search_similar(
            query_vector=query_vector,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=k,
        )

        lc_docs: list[tuple[LCDocument, float]] = []
        for chunk, score in results:
            lc_doc = LCDocument(
                page_content=chunk.content,
                metadata={
                    "id": chunk.id,
                    "document_id": chunk.document_id,
                    "collection_id": chunk.collection_id,
                    "user_id": chunk.user_id,
                    "chunk_index": chunk.chunk_index,
                    "char_count": chunk.char_count,
                    **chunk.chunk_metadata,
                },
            )
            lc_docs.append((lc_doc, score))

        return lc_docs
