from datetime import UTC, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.analysis.hybrid import calculate_hybrid_similarity
from intihal_api.analysis.lexical import WORD_PATTERN, tokenize_words
from intihal_api.core.config import Settings
from intihal_api.corpus.service import FORMAT_BY_CONTENT_TYPE
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
)
from intihal_api.extraction import extract_and_chunk_document
from intihal_api.jobs.states import transition_document
from intihal_api.storage import ObjectStorageService

SNAPSHOT_FIELDS = (
    "algorithm_version",
    "similarity_threshold",
    "word_tfidf_weight",
    "character_tfidf_weight",
    "word_overlap_weight",
)


RETRYABLE_FAILURES = {"processing_failed", "processing_timeout", "retry_exhausted"}


class AnalysisRetryError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def queue_document(document: Document, session: AsyncSession, settings: Settings) -> Analysis:
    """Called with a row lock; admit the workflow durably before broker delivery."""
    latest = await latest_analysis(session, document.id)
    if latest is not None:
        return latest  # start is idempotent even if a fast worker has already failed
    if document.status is not DocumentStatus.UPLOADED:
        raise ValueError("document is not available for analysis")
    return await _enqueue(document, session, settings)


async def retry_document(
    document: Document, failed: Analysis, session: AsyncSession, settings: Settings
) -> Analysis:
    """Called with a refreshed document row lock; one retry per failed analysis ID."""
    if failed.status is not AnalysisStatus.FAILED:
        raise AnalysisRetryError("analysis_retry_conflict")
    latest = await latest_analysis(session, document.id)
    if latest is None:
        raise AnalysisRetryError("analysis_retry_conflict")
    if latest.id != failed.id:
        if latest.status in {
            AnalysisStatus.QUEUED,
            AnalysisStatus.PROCESSING,
            AnalysisStatus.COMPLETED,
        }:
            return latest  # duplicate retry for an old failed run
        raise AnalysisRetryError("analysis_retry_conflict")
    if document.status is not DocumentStatus.FAILED:
        raise AnalysisRetryError("analysis_retry_conflict")
    if failed.failure_reason not in RETRYABLE_FAILURES:
        raise AnalysisRetryError("analysis_retry_not_allowed")
    runs = await session.scalar(
        select(func.count(Analysis.id)).where(Analysis.document_id == document.id)
    )
    if runs - 1 >= settings.analysis_manual_retry_limit:
        raise AnalysisRetryError("analysis_retry_limit")
    return await _enqueue(
        document, session, settings, delay=settings.analysis_manual_retry_delay_seconds
    )


async def _enqueue(
    document: Document, session: AsyncSession, settings: Settings, *, delay: int = 0
) -> Analysis:
    analysis = Analysis(
        id=uuid4(),
        created_at=datetime.now(UTC),
        document_id=document.id,
        status=AnalysisStatus.QUEUED,
        algorithm_version=settings.algorithm_version,
        similarity_threshold=settings.similarity_threshold,
        config_snapshot={field: str(getattr(settings, field)) for field in SNAPSHOT_FIELDS},
    )
    transition_document(document, DocumentStatus.QUEUED)
    document.failure_reason = None
    document.processing_attempts = 0
    document.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
    session.add(analysis)
    await session.commit()
    return analysis


async def latest_analysis(session: AsyncSession, document_id: UUID) -> Analysis | None:
    return await session.scalar(
        select(Analysis)
        .where(Analysis.document_id == document_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(1)
    )


async def extract_document(
    document: Document, analysis: Analysis, session: AsyncSession, storage: ObjectStorageService
) -> None:
    if document.status is DocumentStatus.QUEUED:
        transition_document(document, DocumentStatus.EXTRACTING)
        analysis.status = AnalysisStatus.PROCESSING
        analysis.started_at = datetime.now(UTC)
        await session.commit()
    content = storage.download_object(document.storage_key)
    if len(content) != document.size_bytes or sha256(content).hexdigest() != document.sha256:
        raise ValueError("stored_document_changed")
    extracted = extract_and_chunk_document(
        BytesIO(content), FORMAT_BY_CONTENT_TYPE[document.content_type]
    )
    if not extracted.chunks:
        raise ValueError("no_extractable_text")
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    session.add_all(
        [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
                content_sha256=chunk.content_sha256,
            )
            for chunk in extracted.chunks
        ]
    )
    transition_document(document, DocumentStatus.ANALYZING)
    document.processing_attempts = 0
    document.next_attempt_at = datetime.now(UTC)
    await session.commit()  # chunks and ANALYZING become visible together


def create_matches(
    document_chunks: list[DocumentChunk],
    source_chunks: list[SourceChunk],
    analysis: Analysis,
    settings: Settings,
) -> list[Match]:
    """Store contiguous token evidence, rather than claiming a whole chunk matched."""
    matches = []
    for document_chunk in document_chunks:
        left_spans = tuple(WORD_PATTERN.finditer(document_chunk.content))
        left_tokens = tuple(tokenize_words(token.group())[0] for token in left_spans)
        for source_chunk in source_chunks:
            score = calculate_hybrid_similarity(
                document_chunk.content, source_chunk.content, settings=settings
            ).score
            if Decimal(str(score)) < analysis.similarity_threshold:
                continue
            right_spans = tuple(WORD_PATTERN.finditer(source_chunk.content))
            right_tokens = tuple(tokenize_words(token.group())[0] for token in right_spans)
            for block in SequenceMatcher(
                None, left_tokens, right_tokens, autojunk=False
            ).get_matching_blocks():
                if not block.size:
                    continue
                matches.append(
                    Match(
                        analysis_id=analysis.id,
                        document_chunk_id=document_chunk.id,
                        source_chunk_id=source_chunk.id,
                        method=MatchMethod.HYBRID,
                        similarity_score=Decimal(str(score)).quantize(Decimal("0.0001")),
                        document_match_start=document_chunk.char_start
                        + left_spans[block.a].start(),
                        document_match_end=document_chunk.char_start
                        + left_spans[block.a + block.size - 1].end(),
                        source_match_start=source_chunk.char_start + right_spans[block.b].start(),
                        source_match_end=source_chunk.char_start
                        + right_spans[block.b + block.size - 1].end(),
                        matched_token_count=block.size,
                        explanation="Skor eşiğini geçen parçalardaki ortak ardışık kelimeler.",
                    )
                )
    return matches


async def analyze_document(
    document: Document, analysis: Analysis, session: AsyncSession, settings: Settings
) -> None:
    if not analysis.config_snapshot:
        raise ValueError("missing_algorithm_snapshot")
    configured = Settings(
        _env_file=None,
        **{**settings.model_dump(), **analysis.config_snapshot},
    )
    if configured.algorithm_version != settings.algorithm_version:
        raise ValueError("unsupported_algorithm_version")
    document_chunks = list(
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        )
    )
    if not document_chunks:
        raise ValueError("missing_document_chunks")
    today = datetime.now(UTC).date()
    source_chunks = list(
        await session.scalars(
            select(SourceChunk)
            .join(SourceDocument)
            .where(
                SourceDocument.status == SourceDocumentStatus.READY,
                SourceDocument.license_status == LicenseStatus.APPROVED,
                (SourceDocument.license_valid_from.is_(None))
                | (SourceDocument.license_valid_from <= today),
                (SourceDocument.license_valid_until.is_(None))
                | (SourceDocument.license_valid_until >= today),
            )
            .order_by(SourceChunk.source_document_id, SourceChunk.chunk_index)
        )
    )
    matches = create_matches(document_chunks, source_chunks, analysis, configured)
    await session.execute(delete(Match).where(Match.analysis_id == analysis.id))
    session.add_all(matches)
    transition_document(document, DocumentStatus.COMPLETED)
    document.next_attempt_at = None
    document.failure_reason = None
    analysis.status = AnalysisStatus.COMPLETED
    analysis.completed_at = datetime.now(UTC)
    analysis.failure_reason = None
    await session.commit()  # evidence and completion must be atomic
