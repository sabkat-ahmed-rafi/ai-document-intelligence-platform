from abc import ABC, abstractmethod
from pathlib import Path
from langchain_core.documents import Document as LCDocument


class BaseDocumentParser(ABC):
    """Abstract Base Class for document parsers."""

    @abstractmethod
    async def parse(
        self,
        file_path: str | Path,
        *,
        original_filename: str | None = None,
        mime_type: str | None = None,
    ) -> list[LCDocument]:
        """
        Parses a file into a list of LangChain Document objects.
        Can return full documents (e.g. Markdown) or layout-aware chunks.
        """
        pass
