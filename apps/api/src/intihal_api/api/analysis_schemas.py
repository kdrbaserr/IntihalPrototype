from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


class AnalysisDetailResponse(AnalysisResponse):
    document_status: DocumentStatus
    similarity_threshold: Decimal
    config_snapshot: dict[str, str]
    created_at: datetime
    updated_at: datetime


class EvidenceResponse(BaseModel):
    chunk_id: UUID
    page_number: int | None
    char_start: int
    char_end: int
    text: str


class SourceEvidenceResponse(EvidenceResponse):
    source_document_id: UUID
    title: str
    author: str | None
    publisher: str | None
    source_url: str | None
    license_name: str
    license_url: str | None
    attribution_text: str | None


class MatchResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    method: MatchMethod
    similarity_score: Decimal = Field(ge=0, le=1)
    matched_token_count: int
    explanation: str | None
    document: EvidenceResponse
    source: SourceEvidenceResponse


class MatchPageResponse(BaseModel):
    analysis_id: UUID
    total: int
    limit: int
    offset: int
    items: list[MatchResponse]
