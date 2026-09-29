from decimal import Decimal

import pytest

from intihal_api.analysis import (
    calculate_hybrid_similarity,
    calculate_word_overlap,
    character_ngram_cosine_similarity,
    word_ngram_cosine_similarity,
)
from intihal_api.core.config import Settings


def test_hybrid_score_uses_configured_weights_and_exposes_version() -> None:
    settings = Settings(
        _env_file=None,
        algorithm_version="classical-hybrid-test-v2",
        word_tfidf_weight=Decimal("0.60"),
        character_tfidf_weight=Decimal("0.25"),
        word_overlap_weight=Decimal("0.15"),
    )
    left = "veri bilimi ve yapay zeka"
    right = "veri bilimi uygulaması"

    result = calculate_hybrid_similarity(left, right, settings=settings)
    expected = (
        word_ngram_cosine_similarity(left, right) * 0.60
        + character_ngram_cosine_similarity(left, right) * 0.25
        + calculate_word_overlap(left, right).score * 0.15
    )

    assert result.score == pytest.approx(expected)
    assert result.algorithm_version == "classical-hybrid-test-v2"
    assert result.weights.word_tfidf == Decimal("0.60")
    assert result.weights.character_tfidf == Decimal("0.25")
    assert result.weights.word_overlap == Decimal("0.15")


def test_identical_text_has_maximum_hybrid_score() -> None:
    result = calculate_hybrid_similarity(
        "Aynı örnek metin",
        "Aynı örnek metin",
        settings=Settings(_env_file=None),
    )

    assert result.score == pytest.approx(1.0)
