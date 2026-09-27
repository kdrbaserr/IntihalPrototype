"""MinIO object-storage access and application-level storage errors."""

from intihal_api.storage.service import (
    ObjectStorageService,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageError,
    StorageServiceError,
    StoredObject,
    build_document_storage_key,
    create_object_storage_service,
)

__all__ = [
    "ObjectStorageService",
    "StorageAuthenticationError",
    "StorageConnectionError",
    "StorageError",
    "StorageServiceError",
    "StoredObject",
    "build_document_storage_key",
    "create_object_storage_service",
]
