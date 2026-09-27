from __future__ import annotations

from dataclasses import dataclass
from io import SEEK_SET
from typing import BinaryIO, Protocol
from uuid import UUID

from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import HTTPError

from intihal_api.core.config import Settings

AUTHENTICATION_ERROR_CODES = {
    "AccessDenied",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
}
BUCKET_CREATION_RACE_CODES = {
    "BucketAlreadyExists",
    "BucketAlreadyOwnedByYou",
}


class StorageError(RuntimeError):
    """Safe application-level base error for object-storage failures."""


class StorageConnectionError(StorageError):
    """The storage service could not be reached or stopped responding."""


class StorageAuthenticationError(StorageError):
    """Configured credentials cannot access the requested bucket."""


class StorageServiceError(StorageError):
    """MinIO responded, but could not complete the requested operation."""


class ObjectWriteResult(Protocol):
    etag: str


class StorageClient(Protocol):
    """MinIO operations used by the application storage adapter."""

    def bucket_exists(self, bucket_name: str) -> bool: ...

    def make_bucket(self, bucket_name: str) -> None: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> ObjectWriteResult: ...

    def remove_object(self, bucket_name: str, object_name: str) -> None: ...


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket: str
    key: str
    etag: str


class ObjectStorageService:
    """Own bucket initialization and translate SDK errors into safe app errors."""

    def __init__(self, client: StorageClient, bucket_name: str) -> None:
        self.client = client
        self.bucket_name = bucket_name

    def ensure_bucket(self) -> None:
        """Create the configured bucket once and tolerate simultaneous startup."""

        try:
            if self.client.bucket_exists(self.bucket_name):
                return

            try:
                self.client.make_bucket(self.bucket_name)
            except S3Error as error:
                # Two API instances may both observe a missing bucket.  If the other
                # instance creates it first, the desired end state is already reached.
                if error.code in BUCKET_CREATION_RACE_CODES and self.client.bucket_exists(
                    self.bucket_name
                ):
                    return
                raise self._translate_s3_error(error) from error
        except StorageError:
            raise
        except S3Error as error:
            raise self._translate_s3_error(error) from error
        except (HTTPError, OSError, TimeoutError) as error:
            raise StorageConnectionError(
                "Dosya depolama servisine şu anda ulaşılamıyor."
            ) from error

    def _translate_s3_error(self, error: S3Error) -> StorageError:
        if error.code in AUTHENTICATION_ERROR_CODES:
            return StorageAuthenticationError(
                "Dosya depolama servisi kimlik bilgilerini veya bucket erişimini reddetti."
            )
        return StorageServiceError("Dosya depolama servisi işlemi tamamlayamadı.")

    def upload_object(
        self,
        *,
        key: str,
        stream: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        """Upload a validated stream and return its durable storage identity."""

        stream.seek(0, SEEK_SET)
        try:
            result = self.client.put_object(
                self.bucket_name,
                key,
                stream,
                size_bytes,
                content_type,
            )
            return StoredObject(bucket=self.bucket_name, key=key, etag=result.etag)
        except S3Error as error:
            raise self._translate_s3_error(error) from error
        except (HTTPError, OSError, TimeoutError) as error:
            raise StorageConnectionError(
                "Dosya depolama servisine şu anda ulaşılamıyor."
            ) from error
        finally:
            stream.seek(0, SEEK_SET)

    def remove_object(self, key: str) -> None:
        """Remove an object, primarily to compensate for a failed database write."""

        try:
            self.client.remove_object(self.bucket_name, key)
        except S3Error as error:
            raise self._translate_s3_error(error) from error
        except (HTTPError, OSError, TimeoutError) as error:
            raise StorageConnectionError(
                "Dosya depolama servisine şu anda ulaşılamıyor."
            ) from error


def build_document_storage_key(owner_id: UUID, document_id: UUID) -> str:
    """Build a stable object key without using the untrusted original filename."""

    return f"documents/{owner_id.hex}/{document_id.hex}"


def create_object_storage_service(settings: Settings) -> ObjectStorageService:
    """Build one thread-safe MinIO client for the current API process."""

    http_client = PoolManager(
        timeout=Timeout(
            connect=settings.minio_connect_timeout_seconds,
            read=settings.minio_read_timeout_seconds,
        ),
        retries=Retry(
            total=2,
            connect=2,
            read=0,
            status=0,
            backoff_factor=0.2,
        ),
    )
    client = Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=settings.minio_secure,
        http_client=http_client,
    )
    return ObjectStorageService(client=client, bucket_name=settings.minio_bucket)
