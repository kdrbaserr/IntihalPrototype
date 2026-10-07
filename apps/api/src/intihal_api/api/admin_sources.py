from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from intihal_api.api.dependencies import (
    AdminUser,
    DatabaseSession,
    ObjectStorage,
    require_upload_rate,
)
from intihal_api.core.audit import AuditAction, record_audit
from intihal_api.corpus import (
    SourceChecksumMismatchError,
    SourceDocumentIngestionService,
    SourceDocumentProcessingService,
    SourceMetadata,
    UnsupportedSourceContentTypeError,
)
from intihal_api.db.models import LicenseStatus, SourceDocument, SourceDocumentStatus
from intihal_api.extraction import DocxExtractionError, PdfExtractionError, TextExtractionError
from intihal_api.storage import StorageError
from intihal_api.uploads import (
    InvalidOriginalFilenameError,
    UploadContentChangedError,
    UploadValidationError,
)

router = APIRouter(prefix="/admin/sources", tags=["admin-sources"])


class SourceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str | None
    publisher: str | None
    source_url: str | None
    status: SourceDocumentStatus
    license_status: LicenseStatus
    license_name: str
    rights_holder: str
    license_url: str | None
    attribution_text: str | None
    license_evidence_reference: str
    license_valid_from: date | None
    license_valid_until: date | None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "",
    response_model=SourceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_upload_rate)],
)
async def create_source_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX veya TXT; en fazla 20 MB")],
    title: Annotated[str, Form(max_length=500)],
    license_name: Annotated[str, Form(max_length=255)],
    rights_holder: Annotated[str, Form(max_length=300)],
    license_evidence_reference: Annotated[str, Form(max_length=500)],
    _admin: AdminUser,
    session: DatabaseSession,
    storage: ObjectStorage,
    author: Annotated[str | None, Form(max_length=300)] = None,
    publisher: Annotated[str | None, Form(max_length=300)] = None,
    source_url: Annotated[str | None, Form(max_length=2048)] = None,
    license_url: Annotated[str | None, Form(max_length=2048)] = None,
    attribution_text: Annotated[str | None, Form()] = None,
    license_valid_from: Annotated[date | None, Form()] = None,
    license_valid_until: Annotated[date | None, Form()] = None,
) -> SourceDocument:
    service = SourceDocumentIngestionService(storage)
    try:
        source = await service.create_source(
            metadata=SourceMetadata(
                title=title,
                author=author,
                publisher=publisher,
                source_url=source_url,
                license_name=license_name,
                rights_holder=rights_holder,
                license_url=license_url,
                attribution_text=attribution_text,
                license_evidence_reference=license_evidence_reference,
                license_valid_from=license_valid_from,
                license_valid_until=license_valid_until,
            ),
            filename=file.filename or "",
            content_type=file.content_type,
            stream=file.file,
            session=session,
            actor_id=_admin.id,
        )
        await session.refresh(source)
        return source
    except UploadValidationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except (InvalidOriginalFilenameError, UploadContentChangedError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_source_metadata", "message": str(error)},
        ) from error
    except (PdfExtractionError, DocxExtractionError, TextExtractionError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except StorageError as error:
        raise _storage_unavailable(error) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_conflict",
                "message": "Aynı dosya veya depolama konumu kaynak havuzunda zaten var.",
            },
        ) from error
    finally:
        await file.close()


@router.get("", response_model=list[SourceDocumentResponse])
async def list_source_documents(
    _admin: AdminUser,
    session: DatabaseSession,
    source_status: Annotated[SourceDocumentStatus | None, Query(alias="status")] = None,
    license_status: Annotated[LicenseStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SourceDocument]:
    statement = select(SourceDocument)
    if source_status is not None:
        statement = statement.where(SourceDocument.status == source_status)
    if license_status is not None:
        statement = statement.where(SourceDocument.license_status == license_status)

    sources = await session.scalars(
        statement.order_by(SourceDocument.created_at.desc(), SourceDocument.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = list(sources)
    record_audit(session, action=AuditAction.SOURCE_LIST, actor_id=_admin.id)
    await session.commit()
    return result


@router.post("/{source_id}/disable", response_model=SourceDocumentResponse)
async def disable_source_document(
    source_id: UUID,
    _admin: AdminUser,
    session: DatabaseSession,
) -> SourceDocument:
    source = await _get_source_or_404(source_id, session)
    source.status = SourceDocumentStatus.DISABLED
    record_audit(
        session, action=AuditAction.SOURCE_DISABLE, actor_id=_admin.id, resource_id=source_id
    )
    await session.commit()
    await session.refresh(source)
    return source


@router.post("/{source_id}/reindex", response_model=SourceDocumentResponse)
async def reindex_source_document(
    source_id: UUID,
    _admin: AdminUser,
    session: DatabaseSession,
    storage: ObjectStorage,
) -> SourceDocument:
    source = await _get_source_or_404(source_id, session)
    if source.status is SourceDocumentStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_disabled",
                "message": "Pasif bir kaynak yeniden indekslenemez.",
            },
        )
    if source.status is SourceDocumentStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_processing",
                "message": "Kaynak zaten işleniyor.",
            },
        )

    try:
        content = await run_in_threadpool(
            storage.download_object,
            source.storage_key,
        )
        await SourceDocumentProcessingService().process(
            source_document=source,
            stream=BytesIO(content),
            session=session,
            actor_id=_admin.id,
        )
        await session.refresh(source)
        return source
    except StorageError as error:
        raise _storage_unavailable(error) from error
    except SourceChecksumMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "source_checksum_mismatch", "message": str(error)},
        ) from error
    except (PdfExtractionError, DocxExtractionError, TextExtractionError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except UnsupportedSourceContentTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "unsupported_source_type", "message": str(error)},
        ) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_reindex_conflict",
                "message": "Kaynak parçaları kullanımda olduğu için yeniden indekslenemedi.",
            },
        ) from error


async def _get_source_or_404(source_id: UUID, session: DatabaseSession) -> SourceDocument:
    source = await session.get(SourceDocument, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "source_not_found", "message": "Kaynak belge bulunamadı."},
        )
    return source


def _storage_unavailable(error: StorageError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "storage_unavailable", "message": str(error)},
    )
