import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from intihal_api.analysis import calculate_hybrid_similarity
from intihal_api.core.config import Settings

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "similarity" / "benchmark-v1.json"
EXPECTED_CATEGORIES = {"exact", "minor_edit", "template", "unrelated"}


def load_benchmark() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def test_benchmark_manifest_is_complete_and_versioned() -> None:
    benchmark = load_benchmark()

    assert benchmark["schema_version"] == 1
    assert benchmark["dataset_version"] == "classical-similarity-benchmark-v1"
    assert benchmark["algorithm_version"] == "classical-hybrid-v1"
    assert {case["category"] for case in benchmark["cases"]} == EXPECTED_CATEGORIES
    assert len({case["id"] for case in benchmark["cases"]}) == len(benchmark["cases"])
    assert all(case["purpose"].strip() for case in benchmark["cases"])


def test_versioned_examples_keep_their_golden_scores_and_expected_decisions() -> None:
    benchmark = load_benchmark()
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
