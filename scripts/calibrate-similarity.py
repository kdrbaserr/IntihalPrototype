"""Compare small weight changes on fixed regression labels; no runtime writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import runpy
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


def main() -> None:
    from intihal_api.analysis.hybrid import calculate_hybrid_similarity
    from intihal_api.core.config import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("apps/api/tests/fixtures/similarity/benchmark-v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    evaluate = runpy.run_path(
        str(Path(__file__).with_name("evaluate-similarity-thresholds.py"))
    )["evaluate_threshold"]
    keys = ("word_tfidf", "character_tfidf", "word_overlap")
    baseline = tuple(Decimal(dataset["weights"][key]) for key in keys)
    baseline_threshold = Decimal(dataset["similarity_threshold"])
    delta = Decimal("0.05")
    target_margin = Decimal("0.05")
    candidates = []
    for word_delta in (-delta, Decimal(0), delta):
        for char_delta in (-delta, Decimal(0), delta):
            overlap_delta = -word_delta - char_delta
            if abs(overlap_delta) > delta:
                continue
            weights = tuple(
                old + change
                for old, change in zip(
                    baseline, (word_delta, char_delta, overlap_delta), strict=True
                )
            )
            if any(weight <= 0 or weight >= 1 for weight in weights):
                continue
            settings = Settings.model_validate(
                {
                    "word_tfidf_weight": weights[0],
                    "character_tfidf_weight": weights[1],
                    "word_overlap_weight": weights[2],
                    "similarity_threshold": baseline_threshold,
                    "algorithm_version": dataset["algorithm_version"],
                }
            )
            cases = []
            for case in dataset["cases"]:
                label = case["expected"]["threshold_decision"]
                if label not in {"match", "no_match"}:
                    raise ValueError("Invalid fixed label")
                hybrid = calculate_hybrid_similarity(
                    case["left"], case["right"], settings=settings
                )
                cases.append(
                    {
                        "id": case["id"],
                        "category": case["category"],
                        "label": label,
                        "score": hybrid.score,
                    }
                )
            lower = max(
                Decimal(str(case["score"]))
                for case in cases
                if case["label"] == "no_match"
            )
            upper = min(
                Decimal(str(case["score"]))
                for case in cases
                if case["label"] == "match"
            )
            rows = []
            for index in range(101):
                threshold = Decimal(index) / 100
                row = evaluate(cases, threshold)
                row["positive_margin"] = str(upper - threshold)
                row["negative_margin"] = str(threshold - lower)
                row["meets_margin_policy"] = (
                    upper - threshold >= target_margin
                    and threshold - lower >= target_margin
                )
                rows.append(row)
            eligible = [row for row in rows if row["meets_margin_policy"]]
            if not eligible:
                continue
            best = max(
                eligible,
                key=lambda row: (
                    row["f1"],
                    -abs(Decimal(row["threshold"]) - baseline_threshold),
                    Decimal(row["threshold"]),
                ),
            )
            candidates.append(
                {
                    "weights": dict(zip(keys, map(str, weights), strict=True)),
                    "class_gap": str(upper - lower),
                    "max_negative_score": str(lower),
                    "min_positive_score": str(upper),
                    "weight_l1_change": str(
                        sum(
                            abs(new - old)
                            for new, old in zip(weights, baseline, strict=True)
                        )
                    ),
                    "cases": cases,
                    "thresholds": rows,
                    "best": best,
                    "at_original_threshold": evaluate(cases, baseline_threshold),
                }
            )
    if not candidates:
        raise ValueError("No candidate meets the declared margin policy")
    selected = max(
        candidates,
        key=lambda candidate: (
            candidate["best"]["f1"],
            Decimal(candidate["class_gap"]),
            -Decimal(candidate["weight_l1_change"]),
        ),
    )
    baseline_candidate = next(
        candidate
        for candidate in candidates
        if candidate["weights"] == dataset["weights"]
    )
    result = {
        "schema_version": 1,
        "python_version": platform.python_version(),
        "generated_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "dataset_version": dataset["dataset_version"],
        "label_source": "fixed expected.threshold_decision regression labels",
        "selection_policy": {
            "max_weight_change_per_signal": str(delta),
            "weight_step": str(delta),
            "threshold_step": "0.01",
            "minimum_class_margin": str(target_margin),
            "ranking": "F1, class gap, smallest weight L1 change; nearest original threshold",
            "scope": "in-sample provisional setting; no held-out validation",
        },
        "baseline": {
            "weights": dataset["weights"],
            "threshold": str(baseline_threshold),
            "metrics": baseline_candidate["at_original_threshold"],
            "class_gap": baseline_candidate["class_gap"],
            "cases": baseline_candidate["cases"],
        },
        "selected": selected,
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "weights": selected["weights"],
                "threshold": selected["best"]["threshold"],
                "class_gap": selected["class_gap"],
                "candidates": len(candidates),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
