from __future__ import annotations

from dataclasses import dataclass

from intihal_api.analysis.lexical import tokenize_words


@dataclass(frozen=True, slots=True)
class WordOverlapResult:
    """An explainable Jaccard score over normalized unique words."""

    score: float
    shared_words: tuple[str, ...]
    left_only_words: tuple[str, ...]
    right_only_words: tuple[str, ...]
    intersection_count: int
    union_count: int
    method: str = "jaccard"

    @property
    def calculation(self) -> str:
        """Expose the exact fraction used to produce the score."""

        return f"{self.intersection_count} / {self.union_count}"


def calculate_word_overlap(left: str, right: str) -> WordOverlapResult:
    """Calculate an auditable word-set overlap independently of vector similarity."""

    left_words = set(tokenize_words(left))
    right_words = set(tokenize_words(right))
    shared_words = left_words & right_words
    all_words = left_words | right_words
    intersection_count = len(shared_words)
    union_count = len(all_words)
    score = intersection_count / union_count if union_count else 0.0

    return WordOverlapResult(
        score=score,
        shared_words=tuple(sorted(shared_words)),
        left_only_words=tuple(sorted(left_words - right_words)),
        right_only_words=tuple(sorted(right_words - left_words)),
        intersection_count=intersection_count,
        union_count=union_count,
    )
