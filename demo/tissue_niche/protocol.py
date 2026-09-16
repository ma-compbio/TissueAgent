"""Public input and annotation contracts for the tissue-niche agent comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

PROTOCOL = "tissue_niche_agents_v1"
PROMPT_VERSION = "natural_keys_v4"
LEGACY_PROMPT_VERSION = "guided_v1"
SUPPORTED_PROMPT_VERSIONS = (LEGACY_PROMPT_VERSION, "task_only_v2", "natural_v3", PROMPT_VERSION)
DEFAULT_MODEL = "gpt-5.1"
METHODS = ("tissueagent", "biomni", "spatialagent")
PREDICTION_KEY = "tissue_niche"
UNMATCHED = "Unmatched"


def sha256(path: str | Path) -> str:
    """Hash an artifact without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Write a JSON artifact with stable key ordering."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def public_contract(manifest: dict) -> dict:
    """Select public context explicitly, excluding acquisition and truth metadata."""
    labels = manifest["labels"]
    if not labels or len(set(labels)) != len(labels) or UNMATCHED in labels:
        raise ValueError("labels must contain unique biological classes, excluding Unmatched.")
    return {
        "protocol": PROTOCOL,
        "context": dict(manifest["public_context"]),
        "labels": list(labels),
        "unmatched_label": UNMATCHED,
        "prediction_key": PREDICTION_KEY,
    }


def scientific_prompt(
    contract: dict, query: str, output: str, *, version: str = PROMPT_VERSION
) -> str:
    """Render the shared task, retaining earlier templates for archived evaluation."""
    if version == LEGACY_PROMPT_VERSION:
        return _legacy_scientific_prompt(contract, query, output)
    if version == "task_only_v2":
        return _structured_scientific_prompt(contract, query, output)
    if version not in {"natural_v3", PROMPT_VERSION}:
        raise ValueError(f"Unknown tissue-niche prompt version: {version!r}.")
    context = contract["context"]
    tissue = f"{context['species']} {context['tissue']}"
    if context["tissue"].startswith("developing "):
        tissue = f"developing {context['species']} {context['tissue'].removeprefix('developing ')}"
    expression = {
        "counts": "Gene expression is provided as counts.",
        "log1p normalized expression; do not normalize or log-transform again": (
            "Gene expression is already log-normalized."
        ),
    }[context["expression_state"]]
    details = [expression]
    if disease := context.get("disease"):
        details.append(f"The sample is from a case of {disease}.")
    units = context["coordinate_units"]
    if units != "source spatial coordinate units":
        details.append(f"Spatial coordinates are in {units}.")
    description = "\n".join(details)
    labels = "\n".join(f"- {label}" for label in contract["labels"])
    fields = (
        (
            "Cell-type annotations are in obs['cell_type']; spatial coordinates are in "
            "obsm['spatial'].\n"
        )
        if version == PROMPT_VERSION
        else ""
    )
    return f"""Perform tissue-niche annotation on the {tissue} {context["assay"]}
section in {query}.

The file contains gene expression, existing cell-type annotations, and
spatial coordinates. {description}
{fields}
Assign each cell a label identifying the anatomical tissue region it
belongs to. Choose one of these labels:

{labels}

Use Unmatched when the available evidence does not support assigning
one of these labels.

Save the annotated dataset to {output},
with the per-cell tissue-region labels in obs['tissue_niche'].
"""


def _structured_scientific_prompt(contract: dict, query: str, output: str) -> str:
    return f"""Assign a high-level tissue-niche label to every cell in this spatial dataset.
Dataset context: {json.dumps(contract["context"], ensure_ascii=False, sort_keys=True)}.
Input: {query}
Allowed tissue labels: {json.dumps(contract["labels"], ensure_ascii=False)}.
Use Unmatched when you cannot assign a cell to one of these tissue categories.
Save the annotated H5AD with final labels in obs['tissue_niche'] to {output}.
"""


def _legacy_scientific_prompt(contract: dict, query: str, output: str) -> str:
    return f"""Assign a high-level tissue-niche label to every cell in this spatial dataset.
Dataset context: {json.dumps(contract["context"], ensure_ascii=False, sort_keys=True)}.
Input: {query}
Expression is in X; gene identifiers are in var_names. Supplied cell types are in
obs['cell_type']; cell-centroid coordinates are in obsm['spatial'].
Allowed tissue labels: {json.dumps(contract["labels"], ensure_ascii=False)}.
Use Unmatched when you cannot assign a cell to one of these tissue categories.
Multiple spatial clusters may receive the same high-level tissue label.
Use the supplied expression, cell types and spatial organization to infer tissue niches.
Use the provided cell types as input; preserve them in the output.
Preserve every cell ID, including cells with unknown cell types. Save the annotated H5AD
with final labels in obs['tissue_niche'] to {output}.
"""


def validate_query(path: Path) -> dict:
    """Enforce the complete agent-visible AnnData allowlist at the input boundary."""
    data = ad.read_h5ad(path, backed="r")
    try:
        if list(data.obs.columns) != ["cell_type"] or len(data.var.columns):
            raise ValueError("Query must have only obs['cell_type'] and no var columns.")
        if set(data.obsm) != {"spatial"} or data.uns or data.layers or data.obsp or data.varp:
            raise ValueError("Query contains metadata or arrays outside the allowlist.")
        if data.raw is not None:
            raise ValueError("Query must not contain raw.")
        if not data.obs_names.is_unique or not data.var_names.is_unique:
            raise ValueError("Cell and gene IDs must be unique.")
        if not data.n_obs or not data.n_vars or data.obs["cell_type"].isna().any():
            raise ValueError("Query must contain expression and non-null cell-type labels.")
        coords = np.asarray(data.obsm["spatial"])
        if coords.shape != (data.n_obs, 2) or not np.isfinite(coords).all():
            raise ValueError("Spatial coordinates must be a finite cell-by-two array.")
        for start in range(0, data.n_obs, 10_000):
            values = data.X[start : start + 10_000]
            values = values.data if sparse.issparse(values) else np.asarray(values)
            if not np.isfinite(values).all() or np.any(values < 0):
                raise ValueError("Input expression must be finite and nonnegative.")
        return {"n_cells": data.n_obs, "n_genes": data.n_vars, "query_sha256": sha256(path)}
    finally:
        data.file.close()


def normalize_predictions(raw: pd.Series, labels: list[str]) -> pd.Series:
    """Normalize formatting only; preserve unknown/absent predictions as abstentions."""
    lookup = {label.casefold(): label for label in [*labels, UNMATCHED]}
    return raw.astype("string").str.strip().str.casefold().map(lookup).fillna(UNMATCHED)
