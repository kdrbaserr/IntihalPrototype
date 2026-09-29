import math

import pytest

from intihal_api.analysis import (
    character_ngram_cosine_similarity,
    fit_character_ngram_tfidf,
    generate_character_ngrams,
    normalize_for_character_ngrams,
)


def test_normalizes_case_punctuation_and_repeated_separators() -> None:
    assert normalize_for_character_ngrams("  TÜRKİYE,   Bilimi! ") == "türkiye bilimi"


def test_generates_character_trigrams_through_five_grams() -> None:
    assert generate_character_ngrams("veri") == (
        "ver",
        "eri",
        "veri",
    )


def test_character_tfidf_vectors_are_sparse_and_l2_normalized() -> None:
    model, vectors = fit_character_ngram_tfidf(("mühendislik", "mühendisliği"))

    assert model.vocabulary["müh"] >= 0
    assert vectors[0]
    assert math.isclose(sum(value**2 for value in vectors[0].values()), 1.0)


def test_small_character_change_keeps_partial_similarity() -> None:
    exact = character_ngram_cosine_similarity("mühendislik", "mühendislik")
    typo = character_ngram_cosine_similarity("mühendislik", "mþndislik")
    unrelated = character_ngram_cosine_similarity("mühendislik", "portakal")

    assert exact == pytest.approx(1.0)
    assert 0.0 < typo < exact
    assert unrelated < typo


def test_punctuation_and_case_do_not_change_character_similarity() -> None:
    similarity = character_ngram_cosine_similarity("VERİ, bilimi!", "veri bilimi")

    assert similarity == pytest.approx(1.0)


def test_fitted_model_ignores_unseen_character_fragments() -> None:
    model, _ = fit_character_ngram_tfidf(("bilinen",))

    known, unknown = model.transform(("bilinen", "xyz"))

    assert known
    assert unknown == {}


@pytest.mark.parametrize("ngram_range", [(0, 3), (5, 3), (3, 4, 5), (True, 5)])
def test_rejects_invalid_character_ngram_ranges(ngram_range: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        generate_character_ngrams("metin", ngram_range=ngram_range)  # type: ignore[arg-type]
