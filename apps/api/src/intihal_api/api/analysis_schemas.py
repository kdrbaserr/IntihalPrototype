from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from intihal_api.core.errors import safe_failure_code
from intihal_api.db.models import AnalysisStatus, DocumentStatus, MatchMethod


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: AnalysisStatus
    algorithm_version: str
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None

    @field_validator("failure_reason")
    @classmethod
    def safe_failure(cls, value: str | None) -> str | None:
        return safe_failure_code(value)


class AnalysisDetailResponse(AnalysisResponse):
    document_status: DocumentStatus
    similarity_threshold: Decimal
    config_snapshot: dict[str, str]
    created_at: datetime
    updated_at: datetime


class EvidenceResponse(BaseModel):
    chunk_id: UUID
    page_number: int | None = Field(description="1-based PDF page; null if no reliable page exists")
    char_start: int = Field(ge=0, description="Inclusive offset in normalized full text")
    char_end: int = Field(ge=0, description="Exclusive offset in normalized full text")
    text: str


class SourceEvidenceResponse(EvidenceResponse):
    source_document_id: UUID
    title: str
    original_filename: str
    author: str | None
    publisher: str | None
    source_url: str | None
    license_name: str
    license_url: str | None
    attribution_text: str | None


class ScoreSignalResponse(BaseModel):
    score: Decimal = Field(ge=0, le=1)
    weight: Decimal = Field(ge=0, le=1)
    contribution: Decimal = Field(ge=0, le=1)


class ScoreComponentsResponse(BaseModel):
    scope: Literal["chunk_pair"]
    algorithm_version: str
    word_tfidf: ScoreSignalResponse
    character_tfidf: ScoreSignalResponse
    word_overlap: ScoreSignalResponse


class MatchResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    method: MatchMethod
    similarity_score: Decimal = Field(ge=0, le=1)
    score_components: ScoreComponentsResponse | None = Field(
        default=None, description="Persisted analysis-time signals; null for legacy matches"
    )
    matched_token_count: int
    explanation: str | None
    document: EvidenceResponse
    source: SourceEvidenceResponse


class MatchPageResponse(BaseModel):
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"
    range_convention: Literal["start_inclusive_end_exclusive"] = "start_inclusive_end_exclusive"
    analysis_id: UUID
    total: int
    limit: int
    offset: int
    items: list[MatchResponse]
