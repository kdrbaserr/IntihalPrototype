from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.api.analysis_schemas import (
    AnalysisCreate,
    AnalysisDetailResponse,
    AnalysisResponse,
    EvidenceResponse,
    MatchPageResponse,
    MatchResponse,
    SourceEvidenceResponse,
)
from intihal_api.api.dependencies import CurrentUser, DatabaseSession
from intihal_api.api.document_access import owned_document
from intihal_api.core.config import get_settings
from intihal_api.db.models import (
    Analysis,
    AnalysisStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    Match,
    SourceChunk,
    SourceDocument,
    User,
)
from intihal_api.jobs.workflow import queue_document

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def owned_analysis(
    analysis_id: UUID, user: User, session: AsyncSession
) -> tuple[Analysis, Document]:
    row = (
        await session.execute(
            select(Analysis, Document)
            .join(Document, Analysis.document_id == Document.id)
            .where(
                Analysis.id == analysis_id,
                Document.owner_id == user.id,
                Document.status != DocumentStatus.DELETED,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı.")
    return row.Analysis, row.Document


@router.post("", response_model=AnalysisResponse, status_code=202)
async def create_analysis(
    payload: AnalysisCreate,
    response: Response,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Analysis:
    document = await owned_document(payload.document_id, current_user, session, lock=True)
    try:
        analysis = await queue_document(document, session, get_settings())
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="Belge analiz için uygun durumda değil."
        ) from error
    response.headers["Location"] = f"{get_settings().api_v1_prefix}/analyses/{analysis.id}"
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis(
    analysis_id: UUID, current_user: CurrentUser, session: DatabaseSession
) -> AnalysisDetailResponse:
    analysis, document = await owned_analysis(analysis_id, current_user, session)
    return AnalysisDetailResponse(
        **AnalysisResponse.model_validate(analysis).model_dump(),
        document_status=document.status,
        similarity_threshold=analysis.similarity_threshold,
        config_snapshot=analysis.config_snapshot,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.get("/{analysis_id}/matches", response_model=MatchPageResponse)
async def get_matches(
    analysis_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchPageResponse:
    analysis, _ = await owned_analysis(analysis_id, current_user, session)
    if analysis.status is not AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "analysis_not_completed",
                "message": "Eşleşmeler yalnız tamamlanmış analizlerde okunabilir.",
            },
        )
    total = await session.scalar(
        select(func.count(Match.id)).where(Match.analysis_id == analysis_id)
    )
    rows = (
        await session.execute(
            select(Match, DocumentChunk, SourceChunk, SourceDocument)
            .join(DocumentChunk, Match.document_chunk_id == DocumentChunk.id)
            .join(SourceChunk, Match.source_chunk_id == SourceChunk.id)
            .join(SourceDocument, SourceChunk.source_document_id == SourceDocument.id)
            .where(Match.analysis_id == analysis_id)
            .order_by(Match.similarity_score.desc(), Match.document_match_start, Match.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    items = []
    for match, document_chunk, source_chunk, source in rows:
        items.append(
            MatchResponse(
                id=match.id,
                analysis_id=analysis_id,
                method=match.method,
                similarity_score=match.similarity_score,
                matched_token_count=match.matched_token_count,
                explanation=match.explanation,
                document=EvidenceResponse(
                    chunk_id=document_chunk.id,
                    page_number=document_chunk.page_number,
                    char_start=match.document_match_start,
                    char_end=match.document_match_end,
                    text=document_chunk.content[
                        match.document_match_start
                        - document_chunk.char_start : match.document_match_end
                        - document_chunk.char_start
                    ],
                ),
                source=SourceEvidenceResponse(
                    chunk_id=source_chunk.id,
                    page_number=source_chunk.page_number,
                    char_start=match.source_match_start,
                    char_end=match.source_match_end,
                    text=source_chunk.content[
                        match.source_match_start - source_chunk.char_start : match.source_match_end
                        - source_chunk.char_start
                    ],
                    source_document_id=source.id,
                    title=source.title,
                    author=source.author,
                    publisher=source.publisher,
                    source_url=source.source_url,
                    license_name=source.license_name,
                    license_url=source.license_url,
                    attribution_text=source.attribution_text,
                ),
            )
        )
    return MatchPageResponse(
        analysis_id=analysis_id,
        total=total or 0,
        limit=limit,
        offset=offset,
        items=items,
    )
