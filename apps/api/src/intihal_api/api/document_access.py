"""Owner-scoped queries shared by document, analysis and report-data endpoints."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from intihal_api.db.models import (
    Analysis,
    Document,
    DocumentChunk,
    DocumentStatus,
    Match,
    SourceChunk,
    SourceDocument,
    User,
)


def document_owner_filter(current_user: User) -> ColumnElement[bool]:
    """Administrators have the same ownership boundary as ordinary users."""
    return and_(
        Document.owner_id == current_user.id,
        Document.status != DocumentStatus.DELETED,
    )


def owned_documents_statement(current_user: User) -> Select[tuple[Document]]:
    return select(Document).where(document_owner_filter(current_user))


def owned_analyses_statement(current_user: User) -> Select[tuple[Analysis, Document]]:
    return (
        select(Analysis, Document)
        .join(Document, Analysis.document_id == Document.id)
        .where(document_owner_filter(current_user))
    )


def owned_matches_statement(
    current_user: User,
) -> Select[tuple[Match, DocumentChunk, SourceChunk, SourceDocument]]:
    # Independent foreign keys do not guarantee that a match's chunk belongs to
    # its analysis document. Enforce that relationship before exposing evidence.
    return (
        select(Match, DocumentChunk, SourceChunk, SourceDocument)
        .join(Analysis, Match.analysis_id == Analysis.id)
        .join(Document, Analysis.document_id == Document.id)
        .join(
            DocumentChunk,
            and_(
                Match.document_chunk_id == DocumentChunk.id,
                DocumentChunk.document_id == Analysis.document_id,
            ),
        )
        .join(SourceChunk, Match.source_chunk_id == SourceChunk.id)
        .join(SourceDocument, SourceChunk.source_document_id == SourceDocument.id)
        .where(document_owner_filter(current_user))
    )


async def owned_document(
    document_id: UUID, current_user: User, session: AsyncSession, *, lock: bool = False
) -> Document:
    statement = owned_documents_statement(current_user).where(Document.id == document_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    document = await session.scalar(statement)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found"})
    return document


async def owned_analysis(
    analysis_id: UUID, current_user: User, session: AsyncSession
) -> tuple[Analysis, Document]:
    row = (
        await session.execute(
            owned_analyses_statement(current_user).where(Analysis.id == analysis_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "analysis_not_found"})
    return row.Analysis, row.Document
