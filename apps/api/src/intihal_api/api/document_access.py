from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.db.models import Document, DocumentStatus, User


async def owned_document(
    document_id: UUID, current_user: User, session: AsyncSession, *, lock: bool = False
) -> Document:
    statement = select(Document).where(
        Document.id == document_id,
        Document.owner_id == current_user.id,
        Document.status != DocumentStatus.DELETED,
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    document = await session.scalar(statement)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found"})
    return document
