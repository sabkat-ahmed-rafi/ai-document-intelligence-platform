from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ExtractedEntities(BaseModel):
    """Catalog of structured entities identified within the document."""

    parties: list[str] = Field(
        default_factory=list,
        description="Key organizations, companies, authors, signers, or individuals involved",
        examples=[["Acme Corp", "TechGlobal LLC", "John Doe (CEO)"]],
    )
    dates: list[str] = Field(
        default_factory=list,
        description="Key dates mentioned (effective dates, expiration dates, fiscal quarters, deadlines)",
        examples=[["October 15, 2026", "Q4 2025", "June 30, 2027"]],
    )
    monetary_amounts: list[str] = Field(
        default_factory=list,
        description="Financial numbers, currencies, invoice sums, budgets, penalties, or compensation",
        examples=[["$15,400,000", "€250,000 annual fee", "$500 penalty/day"]],
    )
    document_type: str = Field(
        default="General Document",
        description="Classified document category (e.g. Service Agreement, Invoice, Quarterly Report, Policy)",
        examples=["Master Services Agreement", "Financial Report", "Legal Contract"],
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Primary domain topics, tags, or subject matter keywords",
        examples=[["Enterprise SaaS", "Revenue Growth", "Compliance", "Data Security"]],
    )

    model_config = ConfigDict(from_attributes=True)


class DocumentSummary(BaseModel):
    """Comprehensive executive summary and structured entity intelligence for a document."""

    executive_summary: str = Field(
        ...,
        description="Concise 2-3 paragraph executive summary synthesizing the document's core content and purpose",
    )
    key_takeaways: list[str] = Field(
        default_factory=list,
        description="List of 3-5 critical bullet points or action items",
    )
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities,
        description="Structured entities categorized by parties, dates, financials, type, and topics",
    )
    model: str = Field(..., description="LLM model used for synthesis")
    provider: str = Field(..., description="LLM provider used")
    execution_time_ms: float = Field(..., description="Inference latency in milliseconds")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO timestamp of generation",
    )

    model_config = ConfigDict(from_attributes=True)


class DocumentSummaryResponse(BaseModel):
    """API envelope returned when querying or regenerating a document's summary."""

    document_id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title or original filename")
    has_summary: bool = Field(..., description="Whether a summary has been generated")
    summary: DocumentSummary | None = Field(
        default=None,
        description="The structured summary object if available",
    )

    model_config = ConfigDict(from_attributes=True)
