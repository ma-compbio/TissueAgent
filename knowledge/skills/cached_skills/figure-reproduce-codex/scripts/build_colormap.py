#!/usr/bin/env python3
"""Build a category palette only when every binding has explicit evidence."""

from __future__ import annotations

import argparse
import json
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Resolution:
    """Resolved bindings and their audit evidence."""

    mapping: dict[str, str]
    provenance: dict[str, dict]
    unresolved_dataset_labels: list[str]
    unused_reference_labels: list[str]
    status: str


def normalize_label(value: str) -> str:
    """Normalize typography without making semantic spelling substitutions."""
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def resolve_colormap(
    categories: list[str],
    spec: dict,
    legend_labels: list[str] | None = None,
    aliases: dict[str, str] | None = None,
    allow_exact_positional: bool = False,
) -> Resolution:
    """Bind dataset categories to reference legend entries by reviewed identity."""
    entries = [dict(entry) for entry in spec.get("legend", {}).get("entries", [])]
    aliases = aliases or {}
    if legend_labels is not None:
        if len(legend_labels) != len(entries):
            return Resolution(
                {}, {}, list(categories), list(legend_labels), "legend-label count mismatch"
            )
        for entry, label in zip(entries, legend_labels, strict=True):
            entry["label"] = label
    labeled = all(entry.get("label") for entry in entries)
    if not labeled:
        if not allow_exact_positional or len(entries) != len(categories):
            return Resolution(
                {},
                {},
                list(categories),
                [],
                "unlabeled legend count mismatch or positional binding not authorized",
            )
        for entry, label in zip(entries, categories, strict=True):
            entry["label"] = label

    by_label = {normalize_label(entry["label"]): entry for entry in entries}
    mapping: dict[str, str] = {}
    provenance: dict[str, dict] = {}
    used: set[str] = set()
    unresolved = []
    for category in categories:
        requested = aliases.get(category, category)
        entry = by_label.get(normalize_label(requested))
        if entry is None:
            unresolved.append(category)
            continue
        mapping[category] = entry["hex"].lower()
        used.add(normalize_label(entry["label"]))
        provenance[category] = {
            "reference_label": entry["label"],
            "hex": entry["hex"].lower(),
            "source": "legend-alias" if category in aliases else "legend-label",
            "confidence": float(entry.get("confidence", 0)),
            "swatch_box": entry.get("box"),
        }
    unused = [entry["label"] for entry in entries if normalize_label(entry["label"]) not in used]
    status = "resolved" if not unresolved else "unresolved dataset labels"
    return Resolution(mapping, provenance, unresolved, unused, status)


def _load(path: str | Path):
    path = Path(path)
    text = path.read_text()
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml

        return yaml.safe_load(text)
    except ImportError as exc:
        raise RuntimeError("YAML input requires PyYAML; use JSON instead") from exc


def select_categories(observed: list[str], requested: list[str] | None = None) -> list[str]:
    """Return the reviewed plotted category scope after dataset validation."""
    observed_set = set(observed)
    if requested is None:
        return list(dict.fromkeys(observed))
    missing = [label for label in requested if label not in observed_set]
    if missing:
        raise ValueError(f"plotted categories absent from dataset: {', '.join(missing)}")
    return list(dict.fromkeys(requested))


def _categories(path: str | Path, key: str, requested: list[str] | None = None) -> list[str]:
    path = Path(path)
    if path.suffix.lower() == ".h5ad":
        import anndata

        values = anndata.read_h5ad(path, backed="r").obs[key]
    else:
        import pandas as pd

        values = pd.read_csv(path)[key]
    return select_categories([str(value) for value in values], requested)


def _write_yaml(path: Path, mapping: dict[str, str]) -> None:
    path.write_text(
        "\n".join(f"{json.dumps(key)}: {value}" for key, value in mapping.items()) + "\n"
    )


def main() -> int:
    """Run the colormap builder CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--reference-spec", required=True)
    parser.add_argument("--categories-file")
    parser.add_argument("--legend-labels")
    parser.add_argument("--label-aliases")
    parser.add_argument("--allow-exact-positional", action="store_true")
    parser.add_argument("--provenance-out", required=True)
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    labels = (
        [line.strip() for line in Path(args.legend_labels).read_text().splitlines() if line.strip()]
        if args.legend_labels
        else None
    )
    aliases = _load(args.label_aliases) if args.label_aliases else None
    requested = None
    if args.categories_file:
        requested = [
            line.strip()
            for line in Path(args.categories_file).read_text().splitlines()
            if line.strip()
        ]
    result = resolve_colormap(
        _categories(args.dataset, args.key, requested),
        _load(args.reference_spec),
        labels,
        aliases,
        args.allow_exact_positional,
    )
    Path(args.provenance_out).write_text(json.dumps(asdict(result), indent=2) + "\n")
    if result.unresolved_dataset_labels:
        print(f"ERROR: {result.status}: {', '.join(result.unresolved_dataset_labels)}")
        return 2
    _write_yaml(Path(args.out), result.mapping)
    print(f"wrote {args.out}: {len(result.mapping)} verified category bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
