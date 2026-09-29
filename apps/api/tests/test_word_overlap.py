import pytest

from intihal_api.analysis import calculate_word_overlap


def test_returns_score_and_the_words_that_explain_it() -> None:
    result = calculate_word_overlap("Veri bilimi veri", "veri mühendisliği")

    assert result.score == pytest.approx(1 / 3)
    assert result.shared_words == ("veri",)
    assert result.left_only_words == ("bilimi",)
    assert result.right_only_words == ("mühendisliği",)
    assert result.intersection_count == 1
    assert result.union_count == 3
    assert result.method == "jaccard"
    assert result.calculation == "1 / 3"


def test_normalization_makes_case_and_punctuation_irrelevant() -> None:
    result = calculate_word_overlap("TÜRKİYE'de veri!", "türkiye de veri")

    assert result.score == 1.0
    assert result.shared_words == ("de", "türkiye", "veri")


def test_repeated_words_do_not_artificially_increase_set_overlap() -> None:
    repeated = calculate_word_overlap("veri veri veri bilim", "veri analiz")
    single = calculate_word_overlap("veri bilim", "veri analiz")

    assert repeated == single
    assert repeated.score == pytest.approx(1 / 3)


def test_word_overlap_is_symmetric() -> None:
    forward = calculate_word_overlap("bir iki", "iki üç")
    reverse = calculate_word_overlap("iki üç", "bir iki")

    assert forward.score == reverse.score
    assert forward.shared_words == reverse.shared_words
    assert forward.left_only_words == reverse.right_only_words


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("aynı metin", "aynı metin", 1.0),
        ("ortak yok", "başka ifade", 0.0),
        ("", "", 0.0),
        ("kelime", "", 0.0),
    ],
)
def test_handles_identical_disjoint_and_empty_texts(left: str, right: str, expected: float) -> None:
    assert calculate_word_overlap(left, right).score == expected
