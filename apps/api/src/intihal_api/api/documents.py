from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from intihal_api.api.analysis_schemas import AnalysisResponse
from intihal_api.api.dependencies import CurrentUser, DatabaseSession, ObjectStorage
from intihal_api.api.document_access import (
    owned_analyses_statement,
    owned_document,
    owned_documents_statement,
)
from intihal_api.core.config import get_settings
from intihal_api.core.errors import safe_failure_code
from intihal_api.db.models import Analysis, Document, DocumentStatus
from intihal_api.documents.cleanup import DocumentCleanupError, cleanup_document
from intihal_api.jobs.workflow import queue_document
from intihal_api.storage import StorageError
from intihal_api.uploads import (
    DocumentUploadService,
    InvalidOriginalFilenameError,
    UploadContentChangedError,
    UploadValidationError,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    retention_days: int
    expires_at: datetime
    failure_reason: str | None = None
    latest_analysis_id: UUID | None = None

    @field_validator("failure_reason")
    @classmethod
    def safe_failure(cls, value: str | None) -> str | None:
        return safe_failure_code(value)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX veya TXT; en fazla 20 MB")],
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: ObjectStorage,
    retention_days: Annotated[Literal[7, 30], BeforeValidator(int), Form()] = 7,
) -> Document:
    service = DocumentUploadService(storage)
    try:
        return await service.create_document(
            owner_id=current_user.id,
            filename=file.filename or "",
            content_type=file.content_type,
            stream=file.file,
            session=session,
            retention_days=retention_days,
        )
    except UploadValidationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except (InvalidOriginalFilenameError, UploadContentChangedError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_upload", "message": str(error)},
        ) from error
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "storage_unavailable", "message": str(error)},
        ) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_conflict",
                "message": "Belge kaydı oluşturulamadı; yeniden deneyin.",
            },
        ) from error
    finally:
        await file.close()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Document]:
    documents = await session.scalars(
        owned_documents_statement(current_user)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(documents)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID, current_user: CurrentUser, session: DatabaseSession
) -> DocumentResponse:
    document = await owned_document(document_id, current_user, session)
    latest = await session.scalar(
        owned_analyses_statement(current_user)
        .where(Analysis.document_id == document_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(1)
    )
    return DocumentResponse.model_validate(document).model_copy(
        update={"latest_analysis_id": latest.id if latest else None}
    )


@router.post("/{document_id}/analysis", response_model=AnalysisResponse, status_code=202)
async def start_analysis(document_id: UUID, current_user: CurrentUser, session: DatabaseSession):
    document = await owned_document(document_id, current_user, session, lock=True)
    try:
        return await queue_document(document, session, get_settings())
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": "analysis_not_available"}) from error


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: ObjectStorage,
    response: Response,
) -> None:
    # Unlike read endpoints, deletion can find its owner's tombstone to resume cleanup.
    document = await session.scalar(
        select(Document)
        .where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None:
        raise HTTPException(404, detail={"code": "document_not_found"})
    try:
        await cleanup_document(document, session, storage)
    except DocumentCleanupError as error:
        raise HTTPException(409, detail={"code": error.code}) from error
    except StorageError as error:
        raise HTTPException(503, detail={"code": "document_cleanup_pending"}) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, detail={"code": "document_cleanup_conflict"}) from error
    response.headers["Cache-Control"] = "no-store"
