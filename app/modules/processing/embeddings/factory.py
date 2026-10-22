from langchain_core.embeddings import Embeddings
from core.config import settings


class EmbeddingFactory:
    """Factory for initializing and caching LangChain embedding models."""

    _cached_instance: Embeddings | None = None

    @classmethod
    def get_embeddings(
        cls,
        provider: str | None = None,
        model: str | None = None,
    ) -> Embeddings:
        # If default settings are used, return cached singleton instance
        if provider is None and model is None and cls._cached_instance is not None:
            return cls._cached_instance

        chosen_provider = (provider or settings.EMBEDDING_PROVIDER).lower()
        chosen_model = model or settings.EMBEDDING_MODEL

        if chosen_provider == "fastembed":
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            instance = FastEmbedEmbeddings(model_name=chosen_model)

        elif chosen_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            instance = OpenAIEmbeddings(model=chosen_model)

        elif chosen_provider == "gemini":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            instance = GoogleGenerativeAIEmbeddings(model=chosen_model)

        else:
            raise ValueError(f"Unsupported embedding provider: '{chosen_provider}'")

        if provider is None and model is None:
            cls._cached_instance = instance

        return instance
