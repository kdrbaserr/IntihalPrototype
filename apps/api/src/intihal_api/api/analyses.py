from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func

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
from intihal_api.api.document_access import owned_analysis, owned_document, owned_matches_statement
from intihal_api.core.config import get_settings
from intihal_api.db.models import (
    Analysis,
    AnalysisStatus,
    Match,
)
from intihal_api.jobs.workflow import AnalysisRetryError, queue_document, retry_document

router = APIRouter(prefix="/analyses", tags=["analyses"])


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
        raise HTTPException(status_code=409, detail={"code": "analysis_not_available"}) from error
    response.headers["Location"] = f"{get_settings().api_v1_prefix}/analyses/{analysis.id}"
    return analysis


@router.post("/{analysis_id}/retry", response_model=AnalysisResponse, status_code=202)
async def retry_analysis(
    analysis_id: UUID,
    response: Response,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Analysis:
    failed, document = await owned_analysis(analysis_id, current_user, session)
    document = await owned_document(document.id, current_user, session, lock=True)
    await session.refresh(failed)
    try:
        analysis = await retry_document(document, failed, session, get_settings())
    except AnalysisRetryError as error:
        raise HTTPException(status_code=409, detail={"code": error.code}) from error
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
    # Apply ownership to both the count and evidence query, even after the
    # parent access check. Pagination must never count or expose foreign data.
    statement = owned_matches_statement(current_user).where(Match.analysis_id == analysis_id)
    total = await session.scalar(statement.with_only_columns(func.count(Match.id)))
    rows = (
        await session.execute(
            statement.order_by(Match.similarity_score.desc(), Match.document_match_start, Match.id)
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
                score_components=match.score_components,
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
                    original_filename=source.original_filename,
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
