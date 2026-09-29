from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
DEFAULT_NGRAM_RANGE = (1, 3)
TURKISH_CASE_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})

WordNGram = tuple[str, ...]
SparseVector = dict[int, float]


def tokenize_words(text: str) -> tuple[str, ...]:
    """Return deterministic, case-insensitive Unicode word tokens."""

    normalized = unicodedata.normalize("NFC", text.translate(TURKISH_CASE_TRANSLATION).casefold())
    return tuple(WORD_PATTERN.findall(normalized))


def generate_word_ngrams(
    text: str,
    *,
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE,
) -> tuple[WordNGram, ...]:
    """Generate contiguous word n-grams for every size in the inclusive range."""

    minimum, maximum = _validate_ngram_range(ngram_range)
    tokens = tokenize_words(text)
    return tuple(
        tokens[start : start + size]
        for size in range(minimum, maximum + 1)
        for start in range(len(tokens) - size + 1)
    )


@dataclass(frozen=True, slots=True)
class TfidfModel:
    """A fitted word n-gram vocabulary and its smoothed inverse document frequencies."""

    vocabulary: Mapping[WordNGram, int]
    inverse_document_frequencies: tuple[float, ...]
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE

    def transform(self, documents: Iterable[str]) -> tuple[SparseVector, ...]:
        """Vectorize documents in the fitted feature space and L2-normalize each vector."""

        return tuple(self._transform_one(document) for document in documents)

    def _transform_one(self, document: str) -> SparseVector:
        term_counts = Counter(generate_word_ngrams(document, ngram_range=self.ngram_range))
        weighted = {
            feature_index: term_count * self.inverse_document_frequencies[feature_index]
            for feature, term_count in term_counts.items()
            if (feature_index := self.vocabulary.get(feature)) is not None
        }
        return _l2_normalize(weighted)


def fit_word_ngram_tfidf(
    documents: Iterable[str],
    *,
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE,
) -> tuple[TfidfModel, tuple[SparseVector, ...]]:
    """Fit a word n-gram TF-IDF model and return it with normalized document vectors."""

    document_list = tuple(documents)
    if not document_list:
        raise ValueError("at least one document is required to fit TF-IDF")

    validated_range = _validate_ngram_range(ngram_range)
    document_features = tuple(
        Counter(generate_word_ngrams(document, ngram_range=validated_range))
        for document in document_list
    )
    vocabulary_features = sorted(
        {feature for features in document_features for feature in features},
        key=lambda feature: (len(feature), feature),
    )
    vocabulary = {feature: index for index, feature in enumerate(vocabulary_features)}

    document_frequencies = Counter(
        feature for features in document_features for feature in features.keys()
    )
    document_count = len(document_list)
    inverse_document_frequencies = tuple(
        math.log((1 + document_count) / (1 + document_frequencies[feature])) + 1
        for feature in vocabulary_features
    )
    model = TfidfModel(vocabulary, inverse_document_frequencies, validated_range)
    return model, model.transform(document_list)


def cosine_similarity(
    left: Mapping[int, float],
    right: Mapping[int, float],
) -> float:
    """Measure the angle similarity of two sparse vectors in the closed range [0, 1]."""

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


def word_ngram_cosine_similarity(
    left: str,
    right: str,
    *,
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE,
) -> float:
    """Fit a shared TF-IDF space and compare two texts with cosine similarity."""

    _, vectors = fit_word_ngram_tfidf((left, right), ngram_range=ngram_range)
    return cosine_similarity(vectors[0], vectors[1])


def _validate_ngram_range(ngram_range: Sequence[int]) -> tuple[int, int]:
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


def _l2_normalize(vector: SparseVector) -> SparseVector:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return {}
    return {index: value / norm for index, value in vector.items()}
