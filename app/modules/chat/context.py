import re
from typing import Any

from modules.processing.models import DocumentChunk
from .schemas import CitationSource, RAGContext


class RAGContextBuilder:
    """
    Transforms retrieved database chunks and similarity scores into a structured
    RAGContext object containing:
      1. A numbered, delimited string for LLM prompt injection ([Source 1], [Source 2]).
      2. Structured CitationSource models with page numbers, snippets, and similarity scores.
    """

    @staticmethod
    def extract_page_number(metadata: dict[str, Any] | None) -> int | str | None:
        """
        Extracts human-readable page number or page range from diverse parser metadata formats
        (Docling DOC_CHUNKS, PyPDF, Unstructured, etc.).
        """
        if not metadata:
            return None

        # Direct common keys
        for key in ("page_number", "page", "page_no", "page_idx"):
            if key in metadata and metadata[key] is not None:
                val = metadata[key]
                if isinstance(val, int) and val >= 0:
                    return val + 1 if key == "page_idx" else val
                if isinstance(val, (int, str)):
                    return val

        # Docling dl_meta format: {"dl_meta": {"pages": [1, 2]}} or {"page": 1}
        dl_meta = metadata.get("dl_meta")
        if isinstance(dl_meta, dict):
            pages = dl_meta.get("pages")
            if isinstance(pages, list) and pages:
                if len(pages) == 1:
                    return pages[0]
                return f"{pages[0]}-{pages[-1]}"
            if "page" in dl_meta and dl_meta["page"] is not None:
                return dl_meta["page"]

        # Provenance records (prov: [{"page_no": 1}])
        prov = metadata.get("prov")
        if isinstance(prov, list) and prov and isinstance(prov[0], dict):
            page_no = prov[0].get("page_no")
            if page_no is not None:
                return page_no

        return None

    @staticmethod
    def extract_snippet(content: str, max_chars: int = 200) -> str:
        """
        Extracts a clean, single-line text preview for UI citation tooltips and preview cards.
        """
        clean_text = re.sub(r"\s+", " ", content.strip())
        if len(clean_text) <= max_chars:
            return clean_text
        return clean_text[:max_chars].rstrip() + "..."

    @classmethod
    def build(
        cls,
        chunks_with_scores: list[tuple[DocumentChunk, float]],
        document_titles: dict[str, str] | None = None,
    ) -> RAGContext:
        """
        Builds the unified RAGContext from retrieved chunks and similarity scores.
        """
        if not chunks_with_scores:
            return RAGContext(
                formatted_context="",
                citations=[],
                total_sources=0,
                is_empty=True,
            )

        titles = document_titles or {}
        context_blocks: list[str] = []
        citations: list[CitationSource] = []

        for idx, (chunk, score) in enumerate(chunks_with_scores, start=1):
            doc_title = titles.get(
                chunk.document_id,
                chunk.chunk_metadata.get("original_filename", "Untitled Document"),
            )
            page_num = cls.extract_page_number(chunk.chunk_metadata)
            snippet = cls.extract_snippet(chunk.content)

            citation = CitationSource(
                source_number=idx,
                document_id=chunk.document_id,
                document_title=doc_title,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=page_num,
                snippet=snippet,
                similarity=round(score, 4),
            )
            citations.append(citation)

            page_header = f" | Page: {page_num}" if page_num is not None else ""
            header = f"[Source {idx}] (Document: \"{doc_title}\"{page_header} | Similarity: {score:.2f})"
            block = f"{header}\n{chunk.content.strip()}"
            context_blocks.append(block)

        formatted_context = "\n\n".join(context_blocks)

        return RAGContext(
            formatted_context=formatted_context,
            citations=citations,
            total_sources=len(citations),
            is_empty=False,
        )
