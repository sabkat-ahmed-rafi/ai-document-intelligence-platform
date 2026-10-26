from typing import Any
from langchain_core.language_models.chat_models import BaseChatModel

from core.config import settings
from .exceptions import LLMConfigurationError


DEFAULT_PROVIDER_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "google": "gemini-1.5-flash",
    "ollama": "llama3.2",
}


class LLMFactory:
    """
    Factory for instantiating LangChain chat models based on application settings.
    Supports:
      - Groq (ChatGroq): Ultra-fast inference with Llama 3 models (ideal free-tier choice).
      - OpenAI (ChatOpenAI): GPT-4o, GPT-4o-mini, and any OpenAI-compatible API (DeepSeek, Together, etc.).
      - Google Gemini (ChatGoogleGenerativeAI): Gemini 1.5 Flash, Gemini 1.5 Pro.
      - Ollama (ChatOllama): 100% private, local offline execution without API keys.
    """

    @staticmethod
    def get_chat_model(
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        resolved_provider = (provider or settings.LLM_PROVIDER).strip().lower()

        # If model is explicitly provided, use it.
        # If provider matches settings.LLM_PROVIDER, use settings.LLM_MODEL.
        # Otherwise, fall back to the sensible default model for the chosen provider.
        if model:
            resolved_model = model
        elif resolved_provider == settings.LLM_PROVIDER.strip().lower() and settings.LLM_MODEL:
            resolved_model = settings.LLM_MODEL
        else:
            resolved_model = DEFAULT_PROVIDER_MODELS.get(resolved_provider, "gpt-4o-mini")

        resolved_key = api_key if api_key is not None else settings.LLM_API_KEY
        resolved_base_url = base_url if base_url is not None else settings.LLM_BASE_URL
        resolved_temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        resolved_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

        if resolved_provider == "groq":
            if not resolved_key:
                raise LLMConfigurationError(
                    "Groq LLM provider requires 'LLM_API_KEY' (starts with 'gsk_'). "
                    "Set LLM_API_KEY in your .env file or environment variables."
                )
            from langchain_groq import ChatGroq

            return ChatGroq(
                model=resolved_model or "llama-3.3-70b-versatile",
                api_key=resolved_key,
                temperature=resolved_temp,
                max_tokens=resolved_max_tokens,
                **kwargs,
            )

        if resolved_provider == "openai":
            if not resolved_key and not resolved_base_url:
                raise LLMConfigurationError(
                    "OpenAI LLM provider requires 'LLM_API_KEY' (starts with 'sk-'). "
                    "Set LLM_API_KEY in your .env file or environment variables."
                )
            from langchain_openai import ChatOpenAI

            openai_kwargs: dict[str, Any] = {
                "model": resolved_model or "gpt-4o-mini",
                "temperature": resolved_temp,
                "max_tokens": resolved_max_tokens,
                **kwargs,
            }
            if resolved_key:
                openai_kwargs["api_key"] = resolved_key
            if resolved_base_url:
                openai_kwargs["base_url"] = resolved_base_url

            return ChatOpenAI(**openai_kwargs)

        if resolved_provider in ("gemini", "google"):
            if not resolved_key:
                raise LLMConfigurationError(
                    "Google Gemini LLM provider requires 'LLM_API_KEY'. "
                    "Set LLM_API_KEY in your .env file or environment variables."
                )
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=resolved_model or "gemini-1.5-flash",
                google_api_key=resolved_key,
                temperature=resolved_temp,
                max_output_tokens=resolved_max_tokens,
                **kwargs,
            )

        if resolved_provider == "ollama":
            from langchain_community.chat_models import ChatOllama

            return ChatOllama(
                model=resolved_model or "llama3.2",
                base_url=resolved_base_url or "http://localhost:11434",
                temperature=resolved_temp,
                **kwargs,
            )

        raise LLMConfigurationError(
            f"Unsupported LLM_PROVIDER: '{resolved_provider}'. "
            "Supported providers are: 'groq', 'openai', 'gemini', 'ollama'."
        )


def get_llm() -> BaseChatModel:
    """Convenience helper returning the active LangChain ChatModel instance."""
    return LLMFactory.get_chat_model()
