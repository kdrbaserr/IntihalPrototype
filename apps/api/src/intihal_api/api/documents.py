from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from intihal_api.api.dependencies import CurrentUser, DatabaseSession, ObjectStorage
from intihal_api.db.models import Document, DocumentStatus
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


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX veya TXT; en fazla 20 MB")],
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: ObjectStorage,
) -> Document:
    service = DocumentUploadService(storage)
    try:
        return await service.create_document(
            owner_id=current_user.id,
            filename=file.filename or "",
            content_type=file.content_type,
            stream=file.file,
            session=session,
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
        select(Document)
        .where(
            Document.owner_id == current_user.id,
            Document.status != DocumentStatus.DELETED,
        )
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(documents)
