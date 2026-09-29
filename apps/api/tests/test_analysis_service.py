import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from intihal_api.analysis import AnalysisService
from intihal_api.core.config import Settings
from intihal_api.db.models import Analysis, AnalysisStatus


class RecordingSession:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.fail_commit = fail_commit

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("database unavailable")
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def test_create_analysis_persists_algorithm_version_and_threshold() -> None:
    settings = Settings(
        _env_file=None,
        algorithm_version="classical-hybrid-v7",
        similarity_threshold=Decimal("0.7250"),
    )
    session = RecordingSession()
    document_id = uuid4()

    analysis = asyncio.run(
        AnalysisService(settings).create_analysis(
            document_id=document_id,
            session=session,
        )
    )

    assert session.added == [analysis]
    assert session.committed is True
    assert isinstance(analysis, Analysis)
    assert analysis.document_id == document_id
    assert analysis.status is AnalysisStatus.QUEUED
    assert analysis.algorithm_version == "classical-hybrid-v7"
    assert analysis.similarity_threshold == Decimal("0.7250")


def test_create_analysis_rolls_back_when_persistence_fails() -> None:
    session = RecordingSession(fail_commit=True)

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(
            AnalysisService(Settings(_env_file=None)).create_analysis(
                document_id=uuid4(),
                session=session,
            )
        )

    assert session.rolled_back is True
