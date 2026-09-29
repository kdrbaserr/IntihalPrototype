"""Database engine, sessions, and shared model primitives."""

from intihal_api.db.base import Base, BaseModel, TimestampMixin, UUIDPrimaryKeyMixin
from intihal_api.db.models import (
    Analysis,
    AnalysisStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    LicenseStatus,
    Match,
    MatchMethod,
    SourceChunk,
    SourceDocument,
    SourceDocumentStatus,
    User,
    UserRole,
    UserStatus,
)
from intihal_api.db.session import AsyncSessionFactory, engine, get_db_session

__all__ = [
    "AsyncSessionFactory",
    "Analysis",
    "AnalysisStatus",
    "Base",
    "BaseModel",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "LicenseStatus",
    "Match",
    "MatchMethod",
    "SourceChunk",
    "SourceDocument",
    "SourceDocumentStatus",
    "TimestampMixin",
    "User",
    "UserRole",
    "UserStatus",
    "UUIDPrimaryKeyMixin",
    "engine",
    "get_db_session",
]
