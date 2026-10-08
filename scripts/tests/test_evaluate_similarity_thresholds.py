import runpy
from decimal import Decimal
from pathlib import Path

import pytest

EVALUATE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "evaluate-similarity-thresholds.py")
)["evaluate_threshold"]


def test_raw_score_boundary_is_inclusive_before_database_rounding():
    cases = [{"id": "edit", "label": "match", "score": 0.800889}]
    assert EVALUATE(cases, Decimal("0.800889"))["tp"] == 1
    assert EVALUATE(cases, Decimal("0.8009"))["fn"] == 1


def test_known_confusion_matrix_and_metrics_keep_labels_fixed():
    cases = [
        {"id": "copy", "label": "match", "score": 1.0},
        {"id": "edit", "label": "match", "score": 0.8},
        {"id": "template", "label": "no_match", "score": 0.3},
        {"id": "unrelated", "label": "no_match", "score": 0.01},
    ]
    row = EVALUATE(cases, Decimal("0.3"))
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (2, 1, 0, 1)
    assert row["precision"] == pytest.approx(2 / 3)
    assert row["recall"] == 1
    assert row["f1"] == 0.8
    assert row["specificity"] == 0.5
    assert row["accuracy"] == 0.75
    strict = EVALUATE(cases, Decimal(1))
    assert (strict["tp"], strict["fp"], strict["fn"], strict["tn"]) == (1, 0, 1, 2)
    assert strict["recall"] == 0.5


def test_precision_is_undefined_when_no_matches_predicted():
    row = EVALUATE([{"id": "negative", "label": "no_match", "score": 0.1}], Decimal(1))
    assert row["precision"] is None
    assert row["recall"] is None
    assert row["accuracy"] == 1


@pytest.mark.parametrize("threshold", ["-0.01", "1.01", "NaN", "Infinity"])
def test_invalid_threshold_is_rejected(threshold):
    with pytest.raises(ValueError):
        EVALUATE([], Decimal(threshold))
