import asyncio
from pathlib import Path
from langchain_core.documents import Document as LCDocument
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType

from .base import BaseDocumentParser


class DoclingDocumentParser(BaseDocumentParser):
    """
    Production-grade document parser leveraging IBM's Docling via LangChain.
    Extracts structured layout, tables (as intact Markdown tables), headings, and reading order.
    """

    def __init__(self, export_type: ExportType = ExportType.DOC_CHUNKS):
        self.export_type = export_type

    def _load_sync(self, file_path: str) -> list[LCDocument]:
        loader = DoclingLoader(
            file_path=file_path,
            export_type=self.export_type,
        )
        return loader.load()

    async def parse(
        self,
        file_path: str | Path,
        *,
        original_filename: str | None = None,
        mime_type: str | None = None,
    ) -> list[LCDocument]:
        path_str = str(file_path)
        
        # Execute parsing in a background thread to keep FastAPI event loop responsive
        try:
            docs = await asyncio.to_thread(self._load_sync, path_str)
        except Exception as exc:
            # If DOC_CHUNKS failed for some reason, attempt fallback to MARKDOWN export
            if self.export_type != ExportType.MARKDOWN:
                try:
                    fallback_loader = DoclingLoader(
                        file_path=path_str,
                        export_type=ExportType.MARKDOWN,
                    )
                    docs = await asyncio.to_thread(fallback_loader.load)
                except Exception:
                    raise exc
            else:
                raise exc

        # Enrich metadata
        for d in docs:
            if original_filename:
                d.metadata["original_filename"] = original_filename
            if mime_type:
                d.metadata["mime_type"] = mime_type

        return docs
