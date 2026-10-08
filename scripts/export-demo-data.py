"""Export synthetic demo files without touching accounts, databases or storage."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from intihal_api.analysis import calculate_hybrid_similarity
from intihal_api.core.config import Settings
from intihal_api.corpus.sample_seed import build_sample_sources
from intihal_api.extraction import extract_and_chunk_document
from intihal_api.uploads import validate_document_upload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("demo/v0.1.0"))
    args = parser.parse_args()
    entries = []

    def write(relative: str, content: bytes, **metadata: object) -> None:
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries.append(
            {
                "path": relative,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                **metadata,
            }
        )

    for sample in build_sample_sources():
        source_path = f"sources/{sample.filename}"
        write(
            source_path,
            sample.content,
            role="source",
            content_type=sample.content_type,
            source_metadata=asdict(sample.metadata),
        )
        write(
            f"documents/exact-{sample.filename}",
            sample.content,
            role="user_document",
            content_type=sample.content_type,
            expected="match",
            source=source_path,
        )

    write(
        "documents/unrelated.txt",
        (
            "Satürn çevresindeki halkalar buz parçacıklarından oluşur. "
            "Jüpiter atmosferindeki fırtınalar güçlü rüzgârlarla hareket eder. "
            "Teleskop gözlemleri uzak gezegenlerin yörüngelerini inceler.\n"
        ).encode(),
        role="user_document",
        content_type="text/plain",
        expected="no_match",
    )
    manifest = {
        "schema_version": 1,
        "release": "v0.1.0",
        "synthetic_corpus_version": "v1",
        "algorithm_version": "classical-hybrid-v2",
        "similarity_threshold": "0.7500",
        "weights": {
            "word_tfidf": "0.50",
            "character_tfidf": "0.25",
            "word_overlap": "0.25",
        },
        "license": "CC0-1.0",
        "files": entries,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    settings = Settings(
        _env_file=None,
        algorithm_version=manifest["algorithm_version"],
        similarity_threshold=Decimal(manifest["similarity_threshold"]),
        word_tfidf_weight=Decimal("0.50"),
        character_tfidf_weight=Decimal("0.25"),
        word_overlap_weight=Decimal("0.25"),
    )
    extracted = {}
    for entry in entries:
        data = (args.output / entry["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {entry['path']}")
        validated = validate_document_upload(
            filename=Path(entry["path"]).name,
            content_type=entry["content_type"],
            stream=BytesIO(data),
        )
        extracted[entry["path"]] = extract_and_chunk_document(
            BytesIO(data), validated.document_format
        )
    source_paths = [entry["path"] for entry in entries if entry["role"] == "source"]
    checks = []
    for entry in entries:
        if entry["role"] != "user_document":
            continue
        maximum = max(
            calculate_hybrid_similarity(
                left.content, right.content, settings=settings
            ).score
            for left in extracted[entry["path"]].chunks
            for source_path in source_paths
            for right in extracted[source_path].chunks
        )
        decision = (
            "match" if maximum >= float(settings.similarity_threshold) else "no_match"
        )
        if decision != entry["expected"]:
            raise RuntimeError(f"Unexpected demo decision: {entry['path']}: {maximum}")
        checks.append(
            {
                "path": entry["path"],
                "chunks": len(extracted[entry["path"]].chunks),
                "maximum_chunk_score": maximum,
                "decision": decision,
            }
        )
    verification = {
        "scope": "Local validation, extraction, chunk scoring; not a live API/worker run",
        "manifest_sha256": hashlib.sha256(
            (args.output / "manifest.json").read_bytes()
        ).hexdigest(),
        "algorithm_version": settings.algorithm_version,
        "threshold": str(settings.similarity_threshold),
        "files_checked": len(entries),
        "checks": checks,
    }
    (args.output / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(entries)} synthetic files to {args.output}")


if __name__ == "__main__":
    main()
