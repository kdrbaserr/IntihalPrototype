from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Mapping, Sequence

SparseVector = dict[int, float]


def fit_tfidf_features[Feature: Hashable](
    document_features: Sequence[Counter[Feature]],
    vocabulary_features: Sequence[Feature],
) -> tuple[dict[Feature, int], tuple[float, ...]]:
    vocabulary = {feature: index for index, feature in enumerate(vocabulary_features)}
    document_frequencies = Counter(
        feature for features in document_features for feature in features.keys()
    )
    document_count = len(document_features)
    inverse_document_frequencies = tuple(
        math.log((1 + document_count) / (1 + document_frequencies[feature])) + 1
        for feature in vocabulary_features
    )
    return vocabulary, inverse_document_frequencies


def create_tfidf_vector[Feature: Hashable](
    term_counts: Mapping[Feature, int],
    vocabulary: Mapping[Feature, int],
    inverse_document_frequencies: Sequence[float],
) -> SparseVector:
    weighted = {
        feature_index: term_count * inverse_document_frequencies[feature_index]
        for feature, term_count in term_counts.items()
        if (feature_index := vocabulary.get(feature)) is not None
    }
    return l2_normalize(weighted)


def cosine_similarity(left: Mapping[int, float], right: Mapping[int, float]) -> float:
    """Measure the angle similarity of two non-negative sparse vectors."""

    if not left or not right:
        return 0.0

    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    dot_product = sum(value * larger.get(index, 0.0) for index, value in smaller.items())
    similarity = dot_product / (left_norm * right_norm)
    return min(1.0, max(0.0, similarity))


def validate_ngram_range(ngram_range: Sequence[int]) -> tuple[int, int]:
    if len(ngram_range) != 2:
        raise ValueError("ngram_range must contain exactly two integers")

    minimum, maximum = ngram_range
    if isinstance(minimum, bool) or isinstance(maximum, bool):
        raise ValueError("ngram bounds must be integers")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise ValueError("ngram bounds must be integers")
    if minimum < 1 or maximum < minimum:
        raise ValueError("ngram_range must satisfy 1 <= minimum <= maximum")
    return minimum, maximum


def l2_normalize(vector: SparseVector) -> SparseVector:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return {}
    return {index: value / norm for index, value in vector.items()}
