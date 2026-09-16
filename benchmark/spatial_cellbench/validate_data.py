#!/usr/bin/env python3
"""Validate the frozen eleven-paper spatial benchmark corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from pydantic import BaseModel

from benchmark.spatial_cellbench.schemas import GroundTruthPaper, PublicContext

EXPECTED_PAPERS = 11
CURATION_PROTOCOL = "cellbench_fig12_spatial_v2"
CONTEXT_PROTOCOL = "cellbench_intro_only_v2"


def _read_json_records(path: Path, schema: type[BaseModel]) -> list[BaseModel]:
    """Load and validate a non-empty JSON array."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Expected a non-empty JSON array in {path}")
    return [schema.model_validate(record) for record in payload]


def _read_jsonl(path: Path, schema: type[BaseModel]) -> list[BaseModel]:
    """Compatibility alias for callers; frozen files are JSON arrays."""
    return _read_json_records(path, schema)


def _unique_by_eval_id(records: list[BaseModel], source: Path) -> dict[str, BaseModel]:
    indexed = {}
    for record in records:
        eval_id = record.eval_id
        if eval_id in indexed:
            raise ValueError(f"Duplicate eval_id {eval_id} in {source}")
        indexed[eval_id] = record
    return indexed


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_data(manifest_path: Path, contexts_path: Path, labels_path: Path) -> dict:
    """Validate membership, hashes, curation state, and context leakage boundaries."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    papers = manifest.get("papers", [])
    if len(papers) != EXPECTED_PAPERS:
        raise ValueError(f"Manifest must contain exactly {EXPECTED_PAPERS} spatial papers")
    expected = {paper["opaque_id"] for paper in papers}
    contexts = _unique_by_eval_id(
        _read_json_records(contexts_path, PublicContext),
        contexts_path,
    )
    labels = _unique_by_eval_id(
        _read_json_records(labels_path, GroundTruthPaper),
        labels_path,
    )
    if set(contexts) != expected or set(labels) != expected:
        raise ValueError("Context and ground-truth IDs must match the manifest")

    archive_records = manifest.get("archives", [])
    archive_source_ids = [
        source_id
        for record in archive_records
        for source_id in record.get("source_paper_ids", [])
    ]
    manifest_source_ids = [paper["source_paper_id"] for paper in papers]
    if (
        manifest.get("schema_version") != 3
        or not archive_records
        or len({record.get("filename") for record in archive_records}) != len(archive_records)
        or len(archive_source_ids) != len(set(archive_source_ids))
        or set(archive_source_ids) != set(manifest_source_ids)
    ):
        raise ValueError("Manifest archive provenance is incomplete")

    frozen = manifest.get("frozen_artifacts", {})
    scope_path = manifest_path.parent / "scope_adjudication.json"
    for field, path in (
        ("public_contexts_sha256", contexts_path),
        ("ground_truth_sha256", labels_path),
        ("scope_adjudication_sha256", scope_path),
    ):
        if frozen.get(field) != _sha256(path):
            raise ValueError(f"Frozen artifact hash mismatch: {field}")
    context_version = frozen.get("context_rule_version")
    truth_version = frozen.get("ground_truth_schema_version")
    if truth_version != 2:
        raise ValueError("Unsupported ground-truth schema version")
    if context_version != CONTEXT_PROTOCOL:
        raise ValueError("Unsupported public-context protocol")

    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    if scope.get("protocol") != CURATION_PROTOCOL or scope.get("review_status") != "complete":
        raise ValueError("Spatial scope adjudication is incomplete")
    scope_papers = _unique_by_dict_eval_id(scope.get("papers", []), scope_path)
    if set(scope_papers) != expected:
        raise ValueError("Scope-adjudication IDs must match the manifest")

    total_analyses = 0
    counts = {}
    for eval_id in sorted(expected):
        context = contexts[eval_id]
        truth = labels[eval_id]
        paper = next(item for item in papers if item["opaque_id"] == eval_id)
        if context.context_rule_version != context_version:
            raise ValueError(f"Context rule version mismatch for {eval_id}")
        if context.context.count("\n\n") != 1:
            raise ValueError(
                f"Public context must contain exactly two introduction paragraphs: {eval_id}"
            )
        if "AVAILABLE STUDY INPUTS" in context.context:
            raise ValueError(f"Legacy study-input appendix remains in {eval_id}")
        if len(context.context.split()) != context.word_count:
            raise ValueError(f"Context word count mismatch for {eval_id}")
        if _sha256_text(context.context) != context.context_sha256:
            raise ValueError(f"Context content hash mismatch for {eval_id}")
        forbidden = [paper["source_paper_id"], paper["title"], *paper.get("redaction_terms", [])]
        leaked = [term for term in forbidden if term.casefold() in context.context.casefold()]
        if leaked:
            raise ValueError(f"Context leakage for {eval_id}: {leaked}")
        if truth.schema_version != truth_version:
            raise ValueError(f"Ground-truth schema mismatch for {eval_id}")
        if truth.curation.protocol != CURATION_PROTOCOL:
            raise ValueError(f"Curation protocol mismatch for {eval_id}")
        if truth.curation.adjudication_status != "complete":
            raise ValueError(f"Curation is incomplete for {eval_id}")
        analysis_ids = [analysis.analysis_id for analysis in truth.analyses]
        expected_ids = [f"A{index:02d}" for index in range(1, len(analysis_ids) + 1)]
        if analysis_ids != expected_ids:
            raise ValueError(f"Analysis IDs must be sequential for {eval_id}")
        for analysis in truth.analyses:
            if any(evidence.page > paper["pdf_pages"] for evidence in analysis.evidence):
                raise ValueError(f"Evidence page exceeds PDF length for {eval_id}")
        scope_record = scope_papers[eval_id]
        retained = scope_record.get("retained_id_map", {})
        dropped = scope_record.get("dropped", [])
        dropped_ids = {item.get("source_analysis_id") for item in dropped}
        source_ids = set(retained) | dropped_ids
        original_count = scope_record.get("original_analysis_count")
        expected_source_ids = {
            f"A{index:02d}" for index in range(1, int(original_count or 0) + 1)
        }
        if (
            scope_record.get("final_analysis_count") != len(truth.analyses)
            or set(retained.values()) != set(analysis_ids)
            or len(retained) != len(truth.analyses)
            or set(retained) & dropped_ids
            or source_ids != expected_source_ids
            or any(not item.get("title") or not item.get("reason") for item in dropped)
        ):
            raise ValueError(f"Scope adjudication does not match frozen truth for {eval_id}")
        counts[eval_id] = len(truth.analyses)
        total_analyses += len(truth.analyses)

    summary = manifest.get("curation_summary", {})
    if summary != {
        "included_papers": EXPECTED_PAPERS,
        "final_analysis_labels": total_analyses,
        "analysis_counts": counts,
        "adjudication_status": "complete",
    }:
        raise ValueError("Manifest curation summary does not match frozen truth")
    return {
        "paper_count": EXPECTED_PAPERS,
        "analysis_count": total_analyses,
        "analysis_counts": counts,
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _unique_by_dict_eval_id(records: list[dict], source: Path) -> dict[str, dict]:
    indexed = {}
    for record in records:
        eval_id = record.get("eval_id")
        if not eval_id or eval_id in indexed:
            raise ValueError(f"Missing or duplicate eval_id in {source}")
        indexed[eval_id] = record
    return indexed


def validate_archives(manifest_path: Path, archive_paths: list[Path]) -> dict:
    """Verify every source archive and its assigned paper PDFs."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provided = {path.name: path for path in archive_paths}
    expected = {record["filename"]: record for record in manifest["archives"]}
    if set(provided) != set(expected):
        raise ValueError("Provide every source archive listed in the manifest")

    archive_hashes = {}
    verified_pdfs = 0
    for filename, record in expected.items():
        archive_path = provided[filename]
        archive_hash = _sha256(archive_path)
        if archive_hash != record["sha256"]:
            raise ValueError(f"Source archive hash mismatch: {filename}")
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
        if len(names) != record["member_count"]:
            raise ValueError(f"Source archive member count mismatch: {filename}")
        members = set(names)
        missing = []
        for source_id in record["source_paper_ids"]:
            prefix = f"papers/{source_id}"
            for suffix in ("paper.pdf", "paper.json"):
                member = f"{prefix}/{suffix}"
                if member not in members:
                    missing.append(member)
        if missing:
            raise ValueError(f"Source archive is missing members: {missing}")
        archive_hashes[filename] = archive_hash
        verified_pdfs += len(record["source_paper_ids"])
    return {"archive_sha256": archive_hashes, "verified_pdfs": verified_pdfs}


def main() -> int:
    """Run the corpus validator."""
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=root / "data" / "corpus_manifest.json")
    parser.add_argument("--contexts", type=Path, default=root / "data" / "public_contexts.json")
    parser.add_argument("--labels", type=Path, default=root / "data" / "ground_truth.json")
    parser.add_argument("--archive", type=Path, action="append", dest="archives")
    args = parser.parse_args()
    result = validate_data(args.manifest, args.contexts, args.labels)
    if args.archives:
        result.update(validate_archives(args.manifest, args.archives))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
