from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class DocumentMatchRange(Protocol):
    """A match whose half-open offsets point into the normalized document text."""

    document_match_start: int
    document_match_end: int


@dataclass(frozen=True, slots=True, order=True)
class MatchedInterval:
    """A half-open document interval where ``end`` is not included."""

    start: int
    end: int

    @property
    def character_count(self) -> int:
        return self.end - self.start


type IntervalLike = DocumentMatchRange | MatchedInterval | tuple[int, int]


@dataclass(frozen=True, slots=True)
class OverallSimilarityResult:
    """Unique matched coverage of a normalized document."""

    ratio: float
    percentage: float
    matched_character_count: int
    total_character_count: int
    merged_intervals: tuple[MatchedInterval, ...]
    raw_match_count: int


def merge_match_intervals(
    matches: Iterable[IntervalLike],
    *,
    document_length: int,
) -> tuple[MatchedInterval, ...]:
    """Merge duplicate, overlapping, and adjacent match ranges."""

    if document_length < 0:
        raise ValueError("document length cannot be negative")

    intervals = sorted(_to_interval(match) for match in matches)
    for interval in intervals:
        if interval.start < 0 or interval.end <= interval.start:
            raise ValueError("match ranges must satisfy 0 <= start < end")
        if interval.end > document_length:
            raise ValueError("match range cannot extend beyond the document length")

    merged: list[MatchedInterval] = []
    for interval in intervals:
        if not merged or interval.start > merged[-1].end:
            merged.append(interval)
            continue

        previous = merged[-1]
        merged[-1] = MatchedInterval(previous.start, max(previous.end, interval.end))

    return tuple(merged)


def calculate_overall_similarity(
    matches: Iterable[IntervalLike],
    *,
    document_length: int,
) -> OverallSimilarityResult:
    """Calculate matched document coverage while counting overlaps only once."""

    materialized_matches = tuple(matches)
    merged_intervals = merge_match_intervals(
        materialized_matches,
        document_length=document_length,
    )
    matched_character_count = sum(interval.character_count for interval in merged_intervals)
    ratio = matched_character_count / document_length if document_length else 0.0

    return OverallSimilarityResult(
        ratio=ratio,
        percentage=ratio * 100,
        matched_character_count=matched_character_count,
        total_character_count=document_length,
        merged_intervals=merged_intervals,
        raw_match_count=len(materialized_matches),
    )


def _to_interval(match: IntervalLike) -> MatchedInterval:
    if isinstance(match, MatchedInterval):
        return match
    if isinstance(match, tuple):
        if len(match) != 2:
            raise ValueError("match tuple must contain exactly start and end")
        return MatchedInterval(match[0], match[1])
    return MatchedInterval(match.document_match_start, match.document_match_end)
