"""Read-only verification of a deleted document's database and MinIO cleanup.

Run inside the API container, passing document UUID and analysis UUID as arguments.
"""

import asyncio
import json
import sys
from uuid import UUID

from minio.error import S3Error
from sqlalchemy import func, select

from intihal_api.core.config import get_settings
from intihal_api.db.models import Analysis, Document, DocumentChunk, DocumentStatus, Match
from intihal_api.db.session import AsyncSessionFactory, engine
from intihal_api.storage import create_object_storage_service


async def verify(document_id: UUID, analysis_id: UUID) -> None:
    try:
        async with AsyncSessionFactory() as session:
            document = await session.get(Document, document_id)
            assert document is not None, "Document tombstone missing"
            assert document.status is DocumentStatus.DELETED, "Document is not deleted"
            assert document.cleaned_at is not None, "Cleanup did not finish"
            counts = {}
            for model, condition in (
                (DocumentChunk, DocumentChunk.document_id == document_id),
                (Analysis, Analysis.document_id == document_id),
                (Match, Match.analysis_id == analysis_id),
            ):
                count = await session.scalar(
                    select(func.count()).select_from(model).where(condition)
                )
                assert count == 0, f"Remaining {model.__tablename__}: {count}"
                counts[model.__tablename__] = count
            storage = create_object_storage_service(get_settings())
            try:
                storage.client.stat_object(document.storage_bucket, document.storage_key)
            except S3Error as error:
                assert error.code == "NoSuchKey", f"Unexpected storage response: {error.code}"
            else:
                raise AssertionError("Document file still exists in MinIO")
            print(json.dumps({"document_id": str(document_id), "status": "deleted",
                              "cleaned": True, "remaining": counts, "minio": "NoSuchKey"}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify(UUID(sys.argv[1]), UUID(sys.argv[2])))
