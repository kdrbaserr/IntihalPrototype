import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from intihal_api.analysis import calculate_hybrid_similarity
from intihal_api.core.config import Settings

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "similarity"
BENCHMARK_FILENAME_PATTERN = re.compile(r"benchmark-v(?P<version>[1-9]\d*)\.json")
BENCHMARK_PATHS = tuple(
    sorted(
        FIXTURE_DIRECTORY.glob("benchmark-v*.json"),
        key=lambda path: int(BENCHMARK_FILENAME_PATTERN.fullmatch(path.name)["version"]),
    )
)
EXPECTED_CATEGORIES = {"exact", "minor_edit", "template", "unrelated"}
CATEGORY_ORDER = ("unrelated", "template", "minor_edit", "exact")


def load_benchmark(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_benchmark_settings(benchmark: dict[str, Any]) -> Settings:
    weights = benchmark["weights"]
    return Settings(
        _env_file=None,
        algorithm_version=benchmark["algorithm_version"],
        similarity_threshold=Decimal(benchmark["similarity_threshold"]),
        word_tfidf_weight=Decimal(weights["word_tfidf"]),
        character_tfidf_weight=Decimal(weights["character_tfidf"]),
        word_overlap_weight=Decimal(weights["word_overlap"]),
    )


def test_at_least_one_versioned_benchmark_exists() -> None:
    assert BENCHMARK_PATHS


@pytest.mark.parametrize("benchmark_path", BENCHMARK_PATHS, ids=lambda path: path.stem)
def test_benchmark_manifest_is_complete_and_versioned(benchmark_path: Path) -> None:
    benchmark = load_benchmark(benchmark_path)
    version_match = BENCHMARK_FILENAME_PATTERN.fullmatch(benchmark_path.name)
    assert version_match is not None
    version = version_match["version"]

    assert benchmark["schema_version"] == 1
    assert benchmark["dataset_version"] == f"classical-similarity-benchmark-v{version}"
    assert benchmark["algorithm_version"] == f"classical-hybrid-v{version}"
    assert {case["category"] for case in benchmark["cases"]} == EXPECTED_CATEGORIES
    assert len({case["id"] for case in benchmark["cases"]}) == len(benchmark["cases"])
    assert all(case["purpose"].strip() for case in benchmark["cases"])
    assert all(case["id"].endswith(f"-v{version}") for case in benchmark["cases"])


def test_current_algorithm_defaults_match_the_latest_benchmark_contract() -> None:
    benchmark = load_benchmark(BENCHMARK_PATHS[-1])
    weights = benchmark["weights"]
    fields = Settings.model_fields

    assert fields["algorithm_version"].default == benchmark["algorithm_version"]
    assert fields["similarity_threshold"].default == Decimal(benchmark["similarity_threshold"])
    assert fields["word_tfidf_weight"].default == Decimal(weights["word_tfidf"])
    assert fields["character_tfidf_weight"].default == Decimal(weights["character_tfidf"])
    assert fields["word_overlap_weight"].default == Decimal(weights["word_overlap"])


@pytest.mark.parametrize("benchmark_path", BENCHMARK_PATHS, ids=lambda path: path.stem)
def test_score_bands_are_valid_separated_and_threshold_safe(benchmark_path: Path) -> None:
    benchmark = load_benchmark(benchmark_path)
    threshold = float(benchmark["similarity_threshold"])
    expected_by_category = {case["category"]: case["expected"] for case in benchmark["cases"]}

    for expected in expected_by_category.values():
        assert 0 <= expected["minimum"] <= expected["score"] <= expected["maximum"] <= 1
        if expected["threshold_decision"] == "match":
            assert expected["minimum"] >= threshold
        else:
            assert expected["threshold_decision"] == "no_match"
            assert expected["maximum"] < threshold

    for lower_category, upper_category in zip(CATEGORY_ORDER, CATEGORY_ORDER[1:], strict=False):
        lower = expected_by_category[lower_category]
        upper = expected_by_category[upper_category]
        assert lower["maximum"] < upper["minimum"]


@pytest.mark.parametrize("benchmark_path", BENCHMARK_PATHS, ids=lambda path: path.stem)
def test_versioned_examples_keep_their_golden_scores_and_expected_decisions(
    benchmark_path: Path,
) -> None:
    benchmark = load_benchmark(benchmark_path)
    settings = build_benchmark_settings(benchmark)
    tolerance = benchmark["score_tolerance"]
    observed_scores: dict[str, float] = {}

    for case in benchmark["cases"]:
        result = calculate_hybrid_similarity(case["left"], case["right"], settings=settings)
        expected = case["expected"]
        observed_scores[case["category"]] = result.score

        assert result.algorithm_version == benchmark["algorithm_version"]
        assert result.score == pytest.approx(expected["score"], abs=tolerance)
        assert expected["minimum"] <= result.score <= expected["maximum"]
        decision = "match" if result.score >= float(settings.similarity_threshold) else "no_match"
        assert decision == expected["threshold_decision"]

    assert observed_scores["exact"] > observed_scores["minor_edit"]
    assert observed_scores["minor_edit"] > observed_scores["template"]
    assert observed_scores["template"] > observed_scores["unrelated"]
