import math

import pytest

from intihal_api.analysis import (
    cosine_similarity,
    fit_word_ngram_tfidf,
    generate_word_ngrams,
    tokenize_words,
    word_ngram_cosine_similarity,
)


def test_tokenizes_unicode_words_case_insensitively() -> None:
    assert tokenize_words("Türkçe METİN, sayı 42!") == ("türkçe", "metin", "sayı", "42")


def test_generates_word_unigrams_bigrams_and_trigrams() -> None:
    assert generate_word_ngrams("veri bilimi önemlidir") == (
        ("veri",),
        ("bilimi",),
        ("önemlidir",),
        ("veri", "bilimi"),
        ("bilimi", "önemlidir"),
        ("veri", "bilimi", "önemlidir"),
    )


def test_fits_a_stable_shared_tfidf_feature_space() -> None:
    model, vectors = fit_word_ngram_tfidf(("ortak bir ifade", "ortak başka ifade"))

    assert model.vocabulary[("ortak",)] == 3
    assert len(model.vocabulary) == 10
    assert len(vectors) == 2
    assert math.isclose(sum(value**2 for value in vectors[0].values()), 1.0)


def test_transform_reuses_fitted_vocabulary_and_ignores_unknown_features() -> None:
    model, _ = fit_word_ngram_tfidf(("bilinen kelime",))

    known, unknown = model.transform(("bilinen kelime", "tamamen yabancı"))

    assert known
    assert unknown == {}


def test_cosine_similarity_handles_identical_orthogonal_and_empty_vectors() -> None:
    assert cosine_similarity({0: 1.0, 2: 2.0}, {0: 1.0, 2: 2.0}) == pytest.approx(1.0)
    assert cosine_similarity({0: 1.0}, {1: 1.0}) == 0.0
    assert cosine_similarity({}, {}) == 0.0


def test_word_order_changes_bigram_and_trigram_similarity() -> None:
    identical = word_ngram_cosine_similarity("veri bilimi önemlidir", "veri bilimi önemlidir")
    reordered = word_ngram_cosine_similarity("veri bilimi önemlidir", "önemlidir bilimi veri")

    assert identical == pytest.approx(1.0)
    assert 0.0 < reordered < identical


@pytest.mark.parametrize("ngram_range", [(0, 1), (2, 1), (1, 2, 3), (True, 2)])
def test_rejects_invalid_ngram_ranges(ngram_range: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        generate_word_ngrams("metin", ngram_range=ngram_range)  # type: ignore[arg-type]
