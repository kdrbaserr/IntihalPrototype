from dataclasses import dataclass

import pytest

from intihal_api.analysis import (
    MatchedInterval,
    calculate_overall_similarity,
    merge_match_intervals,
)


@dataclass
class StoredMatch:
    document_match_start: int
    document_match_end: int


def test_overlapping_and_duplicate_matches_are_counted_once() -> None:
    matches = [
        StoredMatch(10, 30),
        StoredMatch(20, 40),
        StoredMatch(10, 30),
        StoredMatch(60, 70),
    ]

    result = calculate_overall_similarity(matches, document_length=100)

    assert result.merged_intervals == (
        MatchedInterval(10, 40),
        MatchedInterval(60, 70),
    )
    assert result.raw_match_count == 4
    assert result.matched_character_count == 40
    assert result.total_character_count == 100
    assert result.ratio == pytest.approx(0.40)
    assert result.percentage == pytest.approx(40.0)


def test_nested_and_adjacent_intervals_form_one_coverage_range() -> None:
    merged = merge_match_intervals(
        [(5, 25), (10, 15), (25, 30), (30, 31)],
        document_length=50,
    )

    assert merged == (MatchedInterval(5, 31),)


def test_no_matches_produce_zero_similarity() -> None:
    result = calculate_overall_similarity([], document_length=125)

    assert result.ratio == 0.0
    assert result.percentage == 0.0
    assert result.matched_character_count == 0
    assert result.merged_intervals == ()


def test_empty_document_without_matches_produces_zero_instead_of_dividing_by_zero() -> None:
    result = calculate_overall_similarity([], document_length=0)

    assert result.ratio == 0.0
    assert result.total_character_count == 0


@pytest.mark.parametrize(
    ("matches", "document_length", "message"),
    [
        ([(0, 1)], -1, "document length cannot be negative"),
        ([(4, 4)], 10, "0 <= start < end"),
        ([(-1, 4)], 10, "0 <= start < end"),
        ([(5, 11)], 10, "beyond the document length"),
    ],
)
def test_invalid_ranges_are_rejected(
    matches: list[tuple[int, int]],
    document_length: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_overall_similarity(matches, document_length=document_length)
