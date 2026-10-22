from abc import ABC, abstractmethod
from langchain_core.documents import Document as LCDocument


class BaseChunker(ABC):
    """Abstract Base Class for text chunkers."""

    @abstractmethod
    def chunk(
        self,
        documents: list[LCDocument],
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[LCDocument]:
        """Splits LangChain documents into smaller contextual chunks."""
        pass
