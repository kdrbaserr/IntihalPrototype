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

DEFAULT_CHARACTER_NGRAM_RANGE = (3, 5)
NON_WORD_PATTERN = re.compile(r"[^\w]+", re.UNICODE)
TURKISH_CASE_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})


def normalize_for_character_ngrams(text: str) -> str:
    """Create a stable character stream while preserving Unicode letters and digits."""

    casefolded = text.translate(TURKISH_CASE_TRANSLATION).casefold()
    normalized = unicodedata.normalize("NFC", casefolded)
    return NON_WORD_PATTERN.sub(" ", normalized).strip()


def generate_character_ngrams(
    text: str,
    *,
    ngram_range: tuple[int, int] = DEFAULT_CHARACTER_NGRAM_RANGE,
) -> tuple[str, ...]:
    """Generate contiguous character n-grams for every size in the inclusive range."""

    minimum, maximum = validate_ngram_range(ngram_range)
    characters = normalize_for_character_ngrams(text)
    return tuple(
        characters[start : start + size]
        for size in range(minimum, maximum + 1)
        for start in range(len(characters) - size + 1)
    )


@dataclass(frozen=True, slots=True)
class CharacterTfidfModel:
    """A fitted character n-gram vocabulary with smoothed IDF weights."""

    vocabulary: Mapping[str, int]
    inverse_document_frequencies: tuple[float, ...]
    ngram_range: tuple[int, int] = DEFAULT_CHARACTER_NGRAM_RANGE

    def transform(self, documents: Iterable[str]) -> tuple[SparseVector, ...]:
        """Vectorize documents in this model's character feature space."""

        return tuple(self._transform_one(document) for document in documents)

    def _transform_one(self, document: str) -> SparseVector:
        term_counts = Counter(generate_character_ngrams(document, ngram_range=self.ngram_range))
        return create_tfidf_vector(term_counts, self.vocabulary, self.inverse_document_frequencies)


def fit_character_ngram_tfidf(
    documents: Iterable[str],
    *,
    ngram_range: tuple[int, int] = DEFAULT_CHARACTER_NGRAM_RANGE,
) -> tuple[CharacterTfidfModel, tuple[SparseVector, ...]]:
    """Fit character n-gram TF-IDF and return normalized document vectors."""

    document_list = tuple(documents)
    if not document_list:
        raise ValueError("at least one document is required to fit TF-IDF")

    validated_range = validate_ngram_range(ngram_range)
    document_features = tuple(
        Counter(generate_character_ngrams(document, ngram_range=validated_range))
        for document in document_list
    )
    vocabulary_features = sorted(
        {feature for features in document_features for feature in features},
        key=lambda feature: (len(feature), feature),
    )
    vocabulary, inverse_document_frequencies = fit_tfidf_features(
        document_features, vocabulary_features
    )
    model = CharacterTfidfModel(vocabulary, inverse_document_frequencies, validated_range)
    return model, model.transform(document_list)


def character_ngram_cosine_similarity(
    left: str,
    right: str,
    *,
    ngram_range: tuple[int, int] = DEFAULT_CHARACTER_NGRAM_RANGE,
) -> float:
    """Compare two texts by their shared character fragments."""

    _, vectors = fit_character_ngram_tfidf((left, right), ngram_range=ngram_range)
    return cosine_similarity(vectors[0], vectors[1])
