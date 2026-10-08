"""Recalculate fixture scores and report threshold effects without changing runtime settings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


def evaluate_threshold(cases: list[dict], threshold: Decimal) -> dict:
    if not threshold.is_finite() or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be finite and between zero and one")
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    decisions = {}
    for case in cases:
        positive = case["label"] == "match"
        predicted = Decimal(str(case["score"])) >= threshold
        key = (
            ("tp" if positive else "fp") if predicted else ("fn" if positive else "tn")
        )
        counts[key] += 1
        decisions[case["id"]] = "match" if predicted else "no_match"
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "threshold": str(threshold),
        **counts,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "specificity": ratio(tn, tn + fp),
        "accuracy": ratio(tp + tn, len(cases)),
        "decisions": decisions,
    }


def score_dataset(dataset: dict) -> list[dict]:
    from intihal_api.analysis.hybrid import calculate_hybrid_similarity
    from intihal_api.core.config import Settings

    weights = dataset["weights"]
    settings = Settings.model_validate(
        {
            "algorithm_version": dataset["algorithm_version"],
            "similarity_threshold": dataset["similarity_threshold"],
            "word_tfidf_weight": weights["word_tfidf"],
            "character_tfidf_weight": weights["character_tfidf"],
            "word_overlap_weight": weights["word_overlap"],
        }
    )
    cases = []
    ids = set()
    for case in dataset["cases"]:
        label = case["expected"]["threshold_decision"]
        if label not in {"match", "no_match"} or case["id"] in ids:
            raise ValueError(
                "Labels must be match/no_match and case IDs must be unique"
            )
        ids.add(case["id"])
        result = calculate_hybrid_similarity(
            case["left"], case["right"], settings=settings
        )
        error = abs(result.score - case["expected"]["score"])
        if error > dataset["score_tolerance"]:
            raise ValueError(f"Golden score drift in {case['id']}: {error}")
        cases.append(
            {
                "id": case["id"],
                "category": case["category"],
                "label": label,
                "score": result.score,
                "golden_score": case["expected"]["score"],
                "golden_absolute_error": error,
                "word_tfidf": result.word_tfidf_score,
                "character_tfidf": result.character_tfidf_score,
                "word_overlap": result.word_overlap.score,
            }
        )
    if {case["label"] for case in cases} != {"match", "no_match"}:
        raise ValueError("Evaluation requires both positive and negative cases")
    return cases


def render_report(result: dict) -> str:
    cases = result["cases"]
    lower = max(case["score"] for case in cases if case["label"] == "no_match")
    upper = min(case["score"] for case in cases if case["label"] == "match")
    baseline = Decimal(result["baseline_threshold"])
    chosen = {
        Decimal(value)
        for value in (
            "0",
            "0.005",
            "0.25",
            "0.2949",
            "0.2950",
            "0.30",
            "0.50",
            "0.75",
            "0.80",
            "0.8008",
            "0.8009",
            "0.801",
            "0.85",
            "1",
        )
    } | {baseline}
    lines = [
        "# Etiketli sette eşik etkisi — 8 Ekim 2026",
        "",
        f"Set: `{result['dataset_version']}`; algoritma: `{result['algorithm_version']}`.",
        f"Çalıştırma (UTC): `{result['generated_at']}`; kaynak commit: `{result['revision']}`.",
        f"Python: `{result['python_version']}`; ortam: `{result['environment']}`.",
        "",
        "## Yöntem ve kapsam",
        "",
        f"Mevcut {len(cases)} sentetik metin çifti yeniden skorlandı. Etiketler fixture içindeki",
        "`expected.threshold_decision` alanından sabit alındı; taranan eşikten türetilmedi.",
        "Bunlar bağımsız uzmanların intihal kararları değil, regresyon beklentileridir.",
        "İki pozitif (kopya/küçük değişiklik), iki negatif (kalıp/ilgisiz) örnek vardır.",
        "Ağırlıklar: sözcük TF-IDF 0,50; karakter TF-IDF 0,30; sözcük örtüşmesi 0,20.",
        "Karar üretimdeki gibi ham skor ≥ eşik karşılaştırmasıyla verildi. Veritabanına",
        "yazılan dört basamaklı yuvarlanmış skor karar için kullanılmadı.",
        f"0–1 arasında 0,01 adımlı tarama ve kritik sınırlar: {len(result['thresholds'])} eşik.",
        "Her örneğin tam skorunda; 1,0 dışındakilerin 0,000000000001 üzerinde de karar kontrol edildi.",
        "JSON bütün skorları/kararları; CSV her eşikte metrikleri içerir.",
        "",
        "## Yeniden hesaplanan skorlar",
        "",
        "| Örnek | Sabit etiket | Ham skor |",
        "|---|---|---:|",
    ]
    for case in cases:
        lines.append(f"| {case['id']} | {case['label']} | {case['score']:.12f} |")
    lines += [
        "",
        "Bütün skorlar fixture toleransı (0,000001) içinde kaldı.",
        "",
        "## Eşik karşılaştırması",
        "",
        "TP: doğru eşleşme; FP: yanlış eşleşme; FN: kaçırılan eşleşme; TN: doğru ret.",
        "Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN).",
        "Accuracy = (TP+TN)/N; specificity = TN/(TN+FP). Sıfır payda JSON/CSV'de boş/null.",
        "",
        "| Eşik | TP | FP | FN | TN | Precision | Recall | F1 | Accuracy |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["thresholds"]:
        if Decimal(row["threshold"]) in chosen:
            metrics = " | ".join(
                f"{row[key]:.1%}" if row[key] is not None else "—"
                for key in ("precision", "recall", "f1", "accuracy")
            )
            lines.append(
                f"| {row['threshold']} | {row['tp']} | {row['fp']} | {row['fn']} "
                f"| {row['tn']} | {metrics} |"
            )
    lines += [
        "",
        "## Bulgular ve sınırlar",
        "",
        f"- Bu sette hatasız aralık: **{lower} < eşik ≤ {upper}**.",
        "  Alt sınır dahil değildir: kalıp skoru eşik ile eşitse yanlış eşleşme olur.",
        f"- Mevcut eşik `{baseline}` bu aralıkta; 2/2 pozitif yakalanır, 2/2 negatif reddedilir.",
        f"- Küçük değişiklik örneğinin mevcut eşiğe marjı yalnızca {upper - float(baseline):.12f}.",
        "  0,8008 geçerken 0,8009 ve 0,801 bu örneği kaçırır; recall %50'ye iner.",
        "- 0,2949 ortak kalıbı yanlış eşleşme kabul eder; 0,2950 reddeder.",
        "- 1,0 tam kopyayı kabul eder; karşılaştırma ≥ olduğu için sınırdaki skor elenmez.",
        "- Tek bir hata accuracy'yi 25 puan değiştirir. Test/kalibrasyon ayrımı, bağımsız",
        "  doğrulama seti, gerçek belge/uzunluk/dil çeşitliliği veya güvenilir saha tahmini yoktur.",
        "  Bu setten üretim için optimum eşik ya da genel başarı oranı çıkarılamaz.",
        "- Çalışma bir skor/karar deneyi; aday kaynak bulma, parçalama ve belge geneli",
        "  benzerlik yüzdesinin doğruluğunu ölçmez. Eşik veya ağırlık ayarı değiştirilmedi.",
        "",
        "## Tekrar çalıştırma",
        "",
        "Proje kökünde (API bağımlılıkları kurulu ortam):",
        "",
        "```powershell",
        "& apps/api/.venv/Scripts/python.exe scripts/evaluate-similarity-thresholds.py `",
        "  --revision (git rev-parse HEAD) --output docs/measurements/2026-10-08-threshold-effects `",
        "  --report docs/threshold-effects-2026-10-08.md",
        "```",
        "",
        f"Fixture SHA-256: `{result['dataset_sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("apps/api/tests/fixtures/similarity/benchmark-v1.json"),
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="JSON/CSV filename prefix"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--revision", default="unknown")
    parser.add_argument("--environment", default="local API virtualenv")
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    cases = score_dataset(dataset)
    thresholds = {Decimal(index) / 100 for index in range(101)}
    thresholds |= {
        Decimal(value)
        for value in (
            "0.005",
            "0.2949",
            "0.2950",
            "0.8008",
            "0.8009",
            "0.801",
            dataset["similarity_threshold"],
        )
    }
    for case in cases:
        score = Decimal(str(case["score"]))
        thresholds.add(score)
        if score + Decimal("0.000000000001") <= 1:
            thresholds.add(score + Decimal("0.000000000001"))
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "revision": args.revision,
        "python_version": platform.python_version(),
        "environment": args.environment,
        "dataset_version": dataset["dataset_version"],
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "algorithm_version": dataset["algorithm_version"],
        "weights": dataset["weights"],
        "baseline_threshold": dataset["similarity_threshold"],
        "label_source": "expected.threshold_decision (fixed regression labels)",
        "comparison": "Decimal(str(raw_score)) >= threshold",
        "cases": cases,
        "thresholds": [
            evaluate_threshold(cases, threshold) for threshold in sorted(thresholds)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with args.output.with_suffix(".csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fields = [key for key in result["thresholds"][0] if key != "decisions"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["thresholds"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(result), encoding="utf-8")
    print(f"{len(cases)} cases; {len(thresholds)} thresholds; report: {args.report}")


if __name__ == "__main__":
    main()
