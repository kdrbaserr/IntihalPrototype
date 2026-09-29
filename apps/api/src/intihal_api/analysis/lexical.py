from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from intihal_api.analysis._vectorization import (
    SparseVector,
    cosine_similarity,
    create_tfidf_vector,
    fit_tfidf_features,
    validate_ngram_range,
)

WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
DEFAULT_NGRAM_RANGE = (1, 3)
TURKISH_CASE_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})

WordNGram = tuple[str, ...]


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

    minimum, maximum = validate_ngram_range(ngram_range)
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
        return create_tfidf_vector(term_counts, self.vocabulary, self.inverse_document_frequencies)


def fit_word_ngram_tfidf(
    documents: Iterable[str],
    *,
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE,
) -> tuple[TfidfModel, tuple[SparseVector, ...]]:
    """Fit a word n-gram TF-IDF model and return it with normalized document vectors."""

    document_list = tuple(documents)
    if not document_list:
        raise ValueError("at least one document is required to fit TF-IDF")

    validated_range = validate_ngram_range(ngram_range)
    document_features = tuple(
        Counter(generate_word_ngrams(document, ngram_range=validated_range))
        for document in document_list
    )
    vocabulary_features = sorted(
        {feature for features in document_features for feature in features},
        key=lambda feature: (len(feature), feature),
    )
    vocabulary, inverse_document_frequencies = fit_tfidf_features(
        document_features, vocabulary_features
    )
    model = TfidfModel(vocabulary, inverse_document_frequencies, validated_range)
    return model, model.transform(document_list)


def word_ngram_cosine_similarity(
    left: str,
    right: str,
    *,
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE,
) -> float:
    """Fit a shared TF-IDF space and compare two texts with cosine similarity."""

    _, vectors = fit_word_ngram_tfidf((left, right), ngram_range=ngram_range)
    return cosine_similarity(vectors[0], vectors[1])
