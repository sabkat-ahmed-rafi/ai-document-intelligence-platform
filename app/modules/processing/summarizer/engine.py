import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from core.config import settings
from infrastructure.llm import get_llm
from .prompts import get_summarization_prompt_template
from .schemas import DocumentSummary, ExtractedEntities

logger = logging.getLogger(__name__)


class DocumentSummarizer:
    """
    Automated Document Summarization & Entity Extraction Engine.
    Uses LangChain LCEL pipelines to generate executive summaries and extract structured
    entities (parties, dates, financial amounts, document classification, topics).
    """

    MAX_DIRECT_CHARS = 30000

    def __init__(
        self,
        llm: BaseChatModel | None = None,
    ):
        self.llm = llm or get_llm()
        self.prompt_template = get_summarization_prompt_template()
        self.output_parser = StrOutputParser()
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

    def _prepare_representative_text(self, chunks_or_text: list[str] | str) -> str:
        """
        Prepares a representative text payload for the LLM.
        For large documents, strategically samples the beginning, middle, and conclusion
        to capture parties, effective dates, core terms, and signatures within token limits.
        """
        if isinstance(chunks_or_text, str):
            if len(chunks_or_text) <= self.MAX_DIRECT_CHARS:
                return chunks_or_text
            # Split into chunks of ~1000 chars for sampling
            chunks = [
                chunks_or_text[i : i + 1000]
                for i in range(0, len(chunks_or_text), 1000)
            ]
        else:
            chunks = chunks_or_text

        if not chunks:
            return ""

        total_length = sum(len(c) for c in chunks)
        if total_length <= self.MAX_DIRECT_CHARS:
            return "\n\n".join(chunks)

        # Strategic sampling for large documents:
        # 1. Beginning (first 8 chunks: title, parties, preamble, scope, dates)
        head = chunks[:8]
        # 2. Conclusion (last 4 chunks: signatures, execution, final terms)
        tail = chunks[-4:] if len(chunks) > 12 else []
        # 3. Middle (sample 6 evenly spaced chunks from the body)
        remaining = chunks[8:-4] if len(chunks) > 12 else []
        middle = []
        if remaining:
            step = max(1, len(remaining) // 6)
            middle = remaining[::step][:6]

        sampled = head + middle + tail
        logger.info(
            f"Sampled {len(sampled)}/{len(chunks)} chunks ({sum(len(c) for c in sampled)} chars) "
            f"for document summarization."
        )
        return "\n\n[...]\n\n".join(sampled)

    def _parse_llm_json(self, raw_text: str) -> dict[str, Any]:
        """Cleans and extracts JSON payload from LLM text response."""
        text = raw_text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        # Direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Regex fallback: find first outer JSON object {...}
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse valid JSON from LLM output. Raw snippet: {text[:200]}")
        return {}

    async def summarize(
        self,
        document_text_or_chunks: list[str] | str,
    ) -> DocumentSummary:
        """
        Executes end-to-end document summarization and entity extraction:
        1. Samples representative document sections if text is large.
        2. Prompts the LLM using structured JSON directives.
        3. Parses output and validates schema into DocumentSummary.
        4. In case of LLM error, falls back to a clean graceful summary without crashing Celery.
        """
        start_time = time.perf_counter()
        model_name, provider = self._resolve_model_metadata()

        context_text = self._prepare_representative_text(document_text_or_chunks)
        if not context_text.strip():
            return DocumentSummary(
                executive_summary="Empty document: no extractable text found.",
                key_takeaways=[],
                entities=ExtractedEntities(),
                model=model_name,
                provider=provider,
                execution_time_ms=0.0,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            raw_output = await self.chain.ainvoke({"document_text": context_text})
            parsed_data = self._parse_llm_json(str(raw_output))

            exec_summary = parsed_data.get("executive_summary") or "Summary could not be generated."
            takeaways = parsed_data.get("key_takeaways") or []
            if not isinstance(takeaways, list):
                takeaways = [str(takeaways)]

            entities_data = parsed_data.get("entities") or {}
            entities = ExtractedEntities(
                parties=entities_data.get("parties", []) if isinstance(entities_data.get("parties"), list) else [],
                dates=entities_data.get("dates", []) if isinstance(entities_data.get("dates"), list) else [],
                monetary_amounts=entities_data.get("monetary_amounts", []) if isinstance(entities_data.get("monetary_amounts"), list) else [],
                document_type=str(entities_data.get("document_type", "General Document")),
                topics=entities_data.get("topics", []) if isinstance(entities_data.get("topics"), list) else [],
            )

            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return DocumentSummary(
                executive_summary=str(exec_summary).strip(),
                key_takeaways=[str(t).strip() for t in takeaways if str(t).strip()],
                entities=entities,
                model=model_name,
                provider=provider,
                execution_time_ms=execution_time_ms,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as exc:
            logger.error(f"Document summarization failed: {exc}", exc_info=True)
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return DocumentSummary(
                executive_summary=f"Automated summary generation encountered an error: {exc}",
                key_takeaways=[],
                entities=ExtractedEntities(document_type="Unclassified"),
                model=model_name,
                provider=provider,
                execution_time_ms=execution_time_ms,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
