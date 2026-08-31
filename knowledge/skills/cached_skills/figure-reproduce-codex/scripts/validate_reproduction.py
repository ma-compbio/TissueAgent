#!/usr/bin/env python3
"""Validate a figure-reproduction artifact set before completion is reported."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(
    target: Path,
    final_figure: Path,
    accepted_attempt: Path,
    plotted_data: Path,
    provenance: Path,
    repro_note: Path,
    attempt_metrics: list[Path],
) -> dict:
    """Validate required artifacts, hashes, palette resolution, and geometry."""
    errors = []
    required = [target, final_figure, accepted_attempt, plotted_data, provenance, repro_note]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required artifact: {path}")
    if (
        final_figure.is_file()
        and accepted_attempt.is_file()
        and _hash(final_figure) != _hash(accepted_attempt)
    ):
        errors.append("final figure hash does not match the accepted attempt")
    provenance_data = {}
    if provenance.is_file():
        try:
            provenance_data = json.loads(provenance.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid provenance JSON: {exc}")
    unresolved = provenance_data.get(
        "unresolved_dataset_labels", provenance_data.get("unresolved", [])
    )
    if unresolved:
        errors.append(f"unresolved palette categories: {', '.join(unresolved)}")
    if not attempt_metrics:
        errors.append("no attempt metrics supplied")
    for metrics_path in attempt_metrics:
        if not metrics_path.is_file():
            errors.append(f"missing attempt metrics: {metrics_path}")
            continue
        try:
            metrics = json.loads(metrics_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid metrics JSON {metrics_path}: {exc}")
            continue
        inputs = metrics.get("inputs", {})
        if target.is_file() and inputs.get("original_sha256") != _hash(target):
            errors.append(f"target hash mismatch in {metrics_path}")
        attempt_name = metrics_path.name.replace("compare_metrics", final_figure.stem).replace(
            ".json", final_figure.suffix
        )
        candidate = final_figure.with_name(attempt_name)
        compared = accepted_attempt if len(attempt_metrics) == 1 else candidate
        if compared.is_file() and inputs.get("reproduced_sha256") != _hash(compared):
            errors.append(f"reproduction hash mismatch in {metrics_path}")
        geometry = metrics.get("pass2_geometry", {})
        if not geometry.get("clean", False):
            errors.append(
                f"structural findings remain in {metrics_path}: {geometry.get('findings', [])}"
            )
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "accepted_attempt": str(accepted_attempt),
        "attempt_count": len(attempt_metrics),
    }


def main() -> int:
    """Run the reproduction validation CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--final-figure", type=Path, required=True)
    parser.add_argument("--accepted-attempt", type=Path, required=True)
    parser.add_argument("--plotted-data", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--repro-note", type=Path, required=True)
    parser.add_argument("--attempt-metrics", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = validate(
        args.target,
        args.final_figure,
        args.accepted_attempt,
        args.plotted_data,
        args.provenance,
        args.repro_note,
        args.attempt_metrics,
    )
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
