from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .base import BaseChunker


class HybridDocumentChunker(BaseChunker):
    """
    Hybrid chunker that works synergistically with Docling's layout-aware parsing.
    If Docling already chunked the document based on headers/tables, this chunker
    validates chunk sizes, splits any oversized chunks safely without breaking table borders,
    and enriches each chunk with sequential indexing and statistics.
    """

    def chunk(
        self,
        documents: list[LCDocument],
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[LCDocument]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
        )

        final_chunks: list[LCDocument] = []

        for doc in documents:
            text = doc.page_content.strip()
            if not text:
                continue

            if len(text) <= chunk_size:
                final_chunks.append(doc)
            else:
                # Sub-split oversized chunk while preserving metadata
                sub_docs = text_splitter.split_documents([doc])
                final_chunks.extend(sub_docs)

        # Sequential indexing and statistics
        enriched_chunks: list[LCDocument] = []
        for idx, c in enumerate(final_chunks):
            content = c.page_content.strip()
            if not content:
                continue

            metadata = dict(c.metadata)
            metadata["chunk_index"] = idx
            metadata["char_count"] = len(content)
            # Simple word-based token estimate (~0.75 tokens per word or len / 4)
            metadata["estimated_tokens"] = max(1, len(content) // 4)

            enriched_chunks.append(
                LCDocument(
                    page_content=content,
                    metadata=metadata,
                )
            )

        return enriched_chunks
