from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from intihal_api.analysis.character import character_ngram_cosine_similarity
from intihal_api.analysis.lexical import word_ngram_cosine_similarity
from intihal_api.analysis.overlap import WordOverlapResult, calculate_word_overlap
from intihal_api.core.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class SimilarityWeights:
    """The configured contribution of each explainable classical signal."""

    word_tfidf: Decimal
    character_tfidf: Decimal
    word_overlap: Decimal

    @classmethod
    def from_settings(cls, settings: Settings) -> SimilarityWeights:
        return cls(
            word_tfidf=settings.word_tfidf_weight,
            character_tfidf=settings.character_tfidf_weight,
            word_overlap=settings.word_overlap_weight,
        )


@dataclass(frozen=True, slots=True)
class HybridSimilarityResult:
    """A reproducible aggregate score together with all of its inputs."""

    score: float
    word_tfidf_score: float
    character_tfidf_score: float
    word_overlap: WordOverlapResult
    weights: SimilarityWeights
    algorithm_version: str


def calculate_hybrid_similarity(
    left: str,
    right: str,
    *,
    settings: Settings | None = None,
) -> HybridSimilarityResult:
    """Combine classical similarity signals using validated runtime configuration."""

    active_settings = settings or get_settings()
    weights = SimilarityWeights.from_settings(active_settings)
    word_tfidf_score = word_ngram_cosine_similarity(left, right)
    character_tfidf_score = character_ngram_cosine_similarity(left, right)
    word_overlap = calculate_word_overlap(left, right)
    score = (
        Decimal(str(word_tfidf_score)) * weights.word_tfidf
        + Decimal(str(character_tfidf_score)) * weights.character_tfidf
        + Decimal(str(word_overlap.score)) * weights.word_overlap
    )

    return HybridSimilarityResult(
        score=min(1.0, max(0.0, float(score))),
        word_tfidf_score=word_tfidf_score,
        character_tfidf_score=character_tfidf_score,
        word_overlap=word_overlap,
        weights=weights,
        algorithm_version=active_settings.algorithm_version,
    )
