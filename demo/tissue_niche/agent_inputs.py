"""Section-level blinded preparation for named tissue-niche annotation."""

from __future__ import annotations

import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import yaml

from .protocol import PROTOCOL, public_contract, sha256, validate_query, write_json

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = Path(__file__).with_name("agent_manifests")
PREPARED_ROOT = ROOT / "demo/data/tissue_niche/agent_prepared"


def load_manifest(dataset_id: str) -> dict:
    """Load a tissue-agent dataset contract independently of clustering manifests."""
    path = MANIFESTS / f"{dataset_id}.yaml"
    manifest = yaml.safe_load(path.read_text())
    if manifest["dataset_id"] != dataset_id:
        raise ValueError("Manifest dataset ID differs from its filename.")
    manifest["manifest_sha256"] = sha256(path)
    return manifest


def prepare_dataset(dataset_id: str, *, output_root: Path = PREPARED_ROOT) -> dict:
    """Prepare all sections and keep truth/ID maps outside public input directories."""
    manifest = load_manifest(dataset_id)
    root = output_root / dataset_id
    metadata_path = root / "preparation.json"
    source = (ROOT / manifest["source_h5ad"]).resolve()
    truth_path = (ROOT / manifest.get("truth_h5ad", manifest["source_h5ad"])).resolve()
    hashes = {
        "source_sha256": sha256(source),
        "truth_source_sha256": sha256(truth_path),
        "manifest_sha256": manifest["manifest_sha256"],
    }
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if metadata["protocol"] != PROTOCOL or any(metadata[k] != v for k, v in hashes.items()):
            raise ValueError("Prepared input provenance changed; prepare into a new output root.")
        for section in metadata["sections"]:
            if (
                validate_query(Path(section["query_h5ad"]))["query_sha256"]
                != section["query_sha256"]
            ):
                raise ValueError("Prepared query was modified.")
        if sha256(metadata["truth_tsv"]) != metadata["truth_sha256"]:
            raise ValueError("Prepared truth was modified.")
        return metadata

    data = ad.read_h5ad(source, backed="r")
    truth_data = ad.read_h5ad(truth_path, backed="r")
    try:
        if list(data.shape) != manifest["expected_shape"]:
            raise ValueError(f"Unexpected source shape: {data.shape}.")
        if not data.obs_names.is_unique or not truth_data.obs_names.is_unique:
            raise ValueError("Source cell IDs must be unique.")
        if set(data.obs_names) != set(truth_data.obs_names):
            raise ValueError("Source and truth cohorts differ.")
        truth = truth_data.obs[manifest["truth_key"]].reindex(data.obs_names).astype("string")
        excluded = truth.isna() | truth.isin(manifest["exclude_truth_labels"])
        unknown = set(truth[~excluded]) - set(manifest["labels"])
        if unknown:
            raise ValueError(f"Unexpected biological truth labels: {sorted(unknown)}.")
        section_key = manifest["section_key"]
        samples = (
            data.obs[section_key].astype("string")
            if section_key
            else pd.Series("all", index=data.obs_names, dtype="string")
        )
        if samples.isna().any():
            raise ValueError("Section identities must not be missing.")
        ids = pd.Index([f"cell_{i:08d}" for i in range(data.n_obs)], name="cell_id")
        private = pd.DataFrame(
            {
                "original_cell_id": data.obs_names,
                "original_section": samples.to_numpy(),
                "ground_truth": truth.to_numpy(),
                "scored": (~excluded).to_numpy(),
            },
            index=ids,
        )
        root.mkdir(parents=True, exist_ok=True)
        contract = public_contract(manifest)
        sections = []
        for number, sample in enumerate(samples.unique(), 1):
            section_id = f"section_{number:03d}"
            indices = np.flatnonzero(samples.to_numpy() == sample)
            public_dir = root / "public" / section_id
            public_dir.mkdir(parents=True, exist_ok=True)
            celltypes = data.obs[manifest["celltype_key"]].iloc[indices].astype("string")
            query = ad.AnnData(
                X=data.X[indices],
                obs=pd.DataFrame(
                    {"cell_type": celltypes.fillna("Unknown").to_numpy()}, index=ids[indices]
                ),
                var=pd.DataFrame(index=pd.Index(data.var_names, name="gene_id")),
                obsm={"spatial": np.asarray(data.obsm[manifest["spatial_key"]])[indices, :2]},
            )
            query_path = public_dir / "query.h5ad"
            query.write_h5ad(query_path, compression="gzip")
            validation = validate_query(query_path)
            write_json(public_dir / "contract.json", contract)
            private.loc[ids[indices], "section_id"] = section_id
            sections.append(
                {
                    "section_id": section_id,
                    "query_h5ad": str(query_path.resolve()),
                    "contract": contract,
                    **validation,
                }
            )
        private_dir = root / "private"
        private_dir.mkdir(exist_ok=True)
        truth_output = private_dir / "ground_truth.tsv"
        private.to_csv(truth_output, sep="\t")
        metadata = {
            "protocol": PROTOCOL,
            "dataset_id": dataset_id,
            **hashes,
            "source_h5ad": str(source),
            "truth_tsv": str(truth_output.resolve()),
            "truth_sha256": sha256(truth_output),
            "n_cells": data.n_obs,
            "n_scored": int((~excluded).sum()),
            "sections": sections,
        }
        write_json(metadata_path, metadata)
        return metadata
    finally:
        data.file.close()
        truth_data.file.close()


def load_prepared(dataset_id: str, *, output_root: Path = PREPARED_ROOT) -> dict:
    """Load a completed preparation without opening original or truth data."""
    metadata = json.loads((output_root / dataset_id / "preparation.json").read_text())
    if metadata["protocol"] != PROTOCOL:
        raise ValueError("Prepared protocol differs from the runner protocol.")
    return metadata
