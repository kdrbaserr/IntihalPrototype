from __future__ import annotations

from typing import Protocol
from uuid import UUID

from intihal_api.core.config import Settings, get_settings
from intihal_api.db.models import Analysis, AnalysisStatus


class AnalysisSession(Protocol):
    def add(self, instance: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class AnalysisService:
    """Create reproducible analysis runs from the active algorithm configuration."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def create_analysis(
        self,
        *,
        document_id: UUID,
        session: AnalysisSession,
    ) -> Analysis:
        analysis = Analysis(
            document_id=document_id,
            status=AnalysisStatus.QUEUED,
            algorithm_version=self.settings.algorithm_version,
            similarity_threshold=self.settings.similarity_threshold,
        )
        try:
            session.add(analysis)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return analysis
