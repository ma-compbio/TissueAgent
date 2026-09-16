"""Prepare the Han whole-mouse-brain Stereo-seq evaluation panel."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import requests
import yaml
from scipy import sparse

from demo.cell_annotation.benchmarks import _label_contract_sha256


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_ID = "han_mouse_brain_stereoseq"
DEFAULT_SOURCE_DIR = REPO_ROOT / "demo" / "data" / "cell_annotation" / "mouse_brain" / DATASET_ID
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "demo"
    / "data"
    / "cell_annotation"
    / "inputs"
    / DATASET_ID
    / "full.h5ad"
)
DEFAULT_MAPPING_OUTPUT = REPO_ROOT / "demo" / "cell_annotation" / "mappings" / f"{DATASET_ID}.json"
DEFAULT_MANIFEST_OUTPUT = (
    REPO_ROOT / "demo" / "cell_annotation" / "manifests" / f"{DATASET_ID}.yaml"
)
REFERENCE_PATH = (
    REPO_ROOT / "workspace" / "project" / "outputs" / "references" / "mouse_cns_reference.h5ad"
)
REFERENCE_SIZE_BYTES = 156_045_969
REFERENCE_SHA256 = "e072db005bff37f2adec571c1938b6cacb37774df0c7a1af206b99039ca59809"
CELLTYPIST_MODEL_PATH = (
    REPO_ROOT / "data" / "cache" / "celltypist" / "data" / "models" / "Mouse_Whole_Brain.pkl"
)
CELLTYPIST_MODEL_SIZE_BYTES = 7_672_163
CELLTYPIST_MODEL_SHA256 = "1e11d918da423015956341e68b56b585ae6e0887da2a23ab8005429e1267ca1f"
CELL_ONTOLOGY_SNAPSHOT_URL = "https://purl.obolibrary.org/obo/cl/releases/2026-06-08/cl.obo"
CELL_ONTOLOGY_SNAPSHOT_FILENAME = "cl-2026-06-08.obo"
CELL_ONTOLOGY_SNAPSHOT_SIZE_BYTES = 17_353_259
CELL_ONTOLOGY_SNAPSHOT_SHA256 = "7e19b4aef8e7fe7720b0c4474c6a5b8713c904ea9ab7b7d5d96f2cb28b8fc51f"
CELL_ONTOLOGY_TERM_NAMES = {
    "CL:0000065": "ependymal cell",
    "CL:0000108": "cholinergic neuron",
    "CL:0000110": "peptidergic neuron",
    "CL:0000115": "endothelial cell",
    "CL:0000127": "astrocyte",
    "CL:0000128": "oligodendrocyte",
    "CL:0000129": "microglial cell",
    "CL:0000540": "neuron",
    "CL:0000617": "GABAergic neuron",
    "CL:0000679": "glutamatergic neuron",
    "CL:0000700": "dopaminergic neuron",
    "CL:0000706": "choroid plexus epithelial cell",
    "CL:0000850": "serotonergic neuron",
    "CL:0002453": "oligodendrocyte precursor cell",
    "CL:0008025": "noradrenergic neuron",
    "CL:0011028": "olfactory ensheathing cell",
    "CL:0011109": "hypocretin-secreting neuron",
    "CL:0011110": "histaminergic neuron",
    "CL:1000042": "forebrain neuroblast",
    "CL:2000089": "dentate gyrus granule cell",
    "CL:4023051": "vascular leptomeningeal cell",
    "CL:4023181": "hypendymal cell",
}

BDSC_DATASET_ID = "1888062851995131906"
BDSC_DATA_CODE = "be9677ed1a3245efbed0d3354e7cdcae"
BDSC_PROJECT_ID = "1710842551940927490"
BDSC_CREATE_USER = "1706651291499872258"
BDSC_APP_ID = "1629164258869"
BDSC_ACCESS_ID = "82obi2rci9slrx4eos0x48v1"
BDSC_CATALOG_URL = (
    "https://www.braindatacenter.cn/api/collect/open/web/"
    f"datasetInfo/getDatasetInfoById?datasetInfoId={BDSC_DATASET_ID}"
)
BDSC_RESOURCE_ROOT = (
    "https://www.braindatacenter.cn/resource/"
    f"{BDSC_APP_ID}/dataset/{BDSC_PROJECT_ID}/{BDSC_CREATE_USER}/{BDSC_DATA_CODE}"
)
ATLAS_ROOT = "https://mouse.digital-brain.cn/spatial-omics/cell"

SELECTED_SECTION_IDS = (
    "T239",
    "T248",
    "T258",
    "T267",
    "T276",
    "T285",
    "T295",
    "T305",
    "T315",
    "T324",
    "T335",
    "T345",
    "T354",
    "T364",
    "T373",
)
SELECTED_SECTION_SOURCE_INDICES = (0, 9, 17, 26, 35, 44, 52, 61, 70, 78, 87, 96, 105, 113, 122)
EXPECTED_SELECTED_CELLS = 478_740
EXPECTED_SELECTED_EXPRESSION_BYTES = 10_639_966_028
EXPECTED_ATLAS_CELLS = 4_209_603
EXPECTED_CLUSTERS = 308
EXPECTED_SUBCLASSES = 19
EXPECTED_MOUSE1_SECTIONS = 123
EXPECTED_CATALOG_FILES = 344
EXPECTED_MOUSE1_EXPRESSION_BYTES = 87_874_980_610
FLAT_ANNOTATION_SIZE_BYTES = 44_238_270


@dataclass(frozen=True)
class PublicArtifact:
    """Immutable identity for one public atlas response."""

    filename: str
    size_bytes: int
    sha256: str
    url: str


PUBLIC_ARTIFACTS = (
    PublicArtifact(
        filename="atlas_cell_types.json",
        size_bytes=40_019,
        sha256="9ae2144c7ee8a0c04fe755fab65685fef9d981a509dd75a3ba3e6329ae1ed15d",
        url=f"{ATLAS_ROOT}/api/v1/samples/cells/types",
    ),
    PublicArtifact(
        filename="atlas_samples.json",
        size_bytes=2_029_465,
        sha256="a102d8863afcdb9359c916948d4cb3805c123969a7249988646ce1427799ff0a",
        url=f"{ATLAS_ROOT}/api/v1/samples/",
    ),
)

SECTION_ARTIFACTS = {
    "T239": (105_274, "eb817ddda9eb24af49c59ff9e909edc0740d5fe4ec4e8ff13e41016c5a176404"),
    "T248": (517_889, "1d40066f30bf565d4c5f8f1486e0a48df7d5f24505b1879e4d740136be21cc82"),
    "T258": (897_364, "bc23eaff51554635fa2f2eb284eb51ced658bd0f84ef686e6ba03c351666df0e"),
    "T267": (883_373, "bc7c309efceee597ea51c3a8ffa9a49096678f596e196bf6100a3fa02b2f3cd8"),
    "T276": (1_174_233, "d30046771c6e6d8a0ba797fb6e09f2f4efec68c042bf2dfa133a5280d7bb4ebe"),
    "T285": (1_923_623, "9d185c09409edeee47a2cde4f4de4333bba7aa58b4b34d19cd7d707967e23c83"),
    "T295": (2_499_381, "ffaab02e866ddb55a0e5abef9c65f15ce3b3af0f3c3db2e7bf5ef3ff20445db9"),
    "T305": (2_863_073, "ce5326924f44f07bfab5bc94a60e3a9e0bcc9e3aa0d5b9a09975ce517b85fce2"),
    "T315": (3_019_499, "13e4822081acecad893c54fc7c5950841a8f3be19c3d0be39931c4f5c7533035"),
    "T324": (3_025_575, "da293aaeab110b38f9dff1dd9c544024634298b956e25ea4824fa467e6a11ce2"),
    "T335": (2_686_585, "3f82d06970ef81201bb6e047c3880c87a128976d67c0886e653d187bf3ccc4c1"),
    "T345": (1_788_421, "8c4ef17300cb79de581024acc9d8e1cb750234f7b5c7454c220373f1aed68f87"),
    "T354": (2_819_205, "7fab830207aaf1e62e8b498404d2773439217104d6f8acbd05a7bacf167f0e08"),
    "T364": (2_038_201, "4f177b2280c62b70357bb88af6317b63d2ee0716ba1fb1565209093a077955cc"),
    "T373": (1_370_597, "007491f79af68cf911dcd3cc2682d3c44f73dd97d2d2ae081de579282eec6c4e"),
}

EXPRESSION_SIZES = {
    "T239": 202_761_535,
    "T248": 345_930_496,
    "T258": 347_895_399,
    "T267": 482_901_542,
    "T276": 554_862_131,
    "T285": 1_041_889_832,
    "T295": 791_723_246,
    "T305": 1_785_786_843,
    "T315": 801_970_004,
    "T324": 740_168_542,
    "T335": 558_227_263,
    "T345": 688_414_926,
    "T354": 993_549_190,
    "T364": 765_632_163,
    "T373": 538_252_916,
}

SOURCE_TO_TARGET = {
    "Astrocytes": "astrocyte",
    "Cerebral nuclei neuroblasts": "cerebral nuclei neuroblast",
    "Cholinergic, monoaminergic, peptidergic neurons": (
        "cholinergic/monoaminergic/peptidergic neuron"
    ),
    "Choroid plexus epithelial cells": "choroid plexus epithelial cell",
    "Dentate gyrus granule neurons": "dentate gyrus granule cell",
    "Di- and mesencephalon neurons": "diencephalon/mesencephalon neuron",
    "Endothelial cells": "endothelial cell",
    "Ependymal cells": "ependymal cell",
    "Hypendymal cells": "hypendymal cell",
    "Microglia": "microglial cell",
    "Olfactory bulb excitatory neurons": "olfactory bulb excitatory neuron",
    "Olfactory bulb inhibitory neurons": "olfactory bulb inhibitory neuron",
    "Olfactory ensheathing cells": "olfactory ensheathing cell",
    "Oligodendrocyte precursor cells": "oligodendrocyte precursor cell",
    "Oligodendrocytes": "oligodendrocyte",
    "Rhombencephalon neurons": "rhombencephalon neuron",
    "Telencephalon excitatory neurons": "telencephalon excitatory neuron",
    "Telencephalon inhibitory neurons": "telencephalon inhibitory neuron",
    "Vascular and leptomeningeal cells": "vascular leptomeningeal cell",
}

TARGET_LABEL_DEFINITIONS = {
    "astrocyte": {
        "cell_ontology_term_ids": ["CL:0000127"],
        "ontology_relation": "exact",
        "definition": "Astrocyte.",
    },
    "cerebral nuclei neuroblast": {
        "cell_ontology_term_ids": ["CL:1000042"],
        "ontology_relation": "broader",
        "definition": "Forebrain neuroblast qualified to the cerebral nuclei source branch.",
    },
    "cholinergic/monoaminergic/peptidergic neuron": {
        "cell_ontology_term_ids": [
            "CL:0000540",
            "CL:0000108",
            "CL:0000110",
            "CL:0011110",
            "CL:0000700",
            "CL:0000850",
            "CL:0008025",
            "CL:0011109",
        ],
        "ontology_relation": "composite",
        "definition": (
            "Publisher composite of cholinergic, histaminergic, dopaminergic, "
            "serotonergic, noradrenergic, hypocretin-secreting, and other peptidergic neurons."
        ),
    },
    "choroid plexus epithelial cell": {
        "cell_ontology_term_ids": ["CL:0000706"],
        "ontology_relation": "exact",
        "definition": "Choroid plexus epithelial cell.",
    },
    "dentate gyrus granule cell": {
        "cell_ontology_term_ids": ["CL:2000089"],
        "ontology_relation": "exact",
        "definition": "Granule cell of the dentate gyrus.",
    },
    "diencephalon/mesencephalon neuron": {
        "cell_ontology_term_ids": ["CL:0000540"],
        "ontology_relation": "broader",
        "definition": "Neuron from a mixed transmitter diencephalon or mesencephalon branch.",
    },
    "endothelial cell": {
        "cell_ontology_term_ids": ["CL:0000115"],
        "ontology_relation": "exact",
        "definition": "Endothelial cell.",
    },
    "ependymal cell": {
        "cell_ontology_term_ids": ["CL:0000065"],
        "ontology_relation": "exact",
        "definition": "Ependymal cell.",
    },
    "hypendymal cell": {
        "cell_ontology_term_ids": ["CL:4023181"],
        "ontology_relation": "exact",
        "definition": "Hypendymal cell.",
    },
    "microglial cell": {
        "cell_ontology_term_ids": ["CL:0000129"],
        "ontology_relation": "exact",
        "definition": "Microglial cell.",
    },
    "olfactory bulb excitatory neuron": {
        "cell_ontology_term_ids": ["CL:0000679"],
        "ontology_relation": "broader",
        "definition": "Glutamatergic neuron qualified to the olfactory bulb source branch.",
    },
    "olfactory bulb inhibitory neuron": {
        "cell_ontology_term_ids": ["CL:0000617"],
        "ontology_relation": "broader",
        "definition": "GABAergic neuron qualified to the olfactory bulb source branch.",
    },
    "olfactory ensheathing cell": {
        "cell_ontology_term_ids": ["CL:0011028"],
        "ontology_relation": "exact",
        "definition": "Olfactory ensheathing cell.",
    },
    "oligodendrocyte precursor cell": {
        "cell_ontology_term_ids": ["CL:0002453"],
        "ontology_relation": "exact",
        "definition": "Oligodendrocyte precursor cell.",
    },
    "oligodendrocyte": {
        "cell_ontology_term_ids": ["CL:0000128"],
        "ontology_relation": "exact",
        "definition": "Oligodendrocyte.",
    },
    "rhombencephalon neuron": {
        "cell_ontology_term_ids": ["CL:0000540"],
        "ontology_relation": "broader",
        "definition": (
            "Neuron from a mixed transmitter rhombencephalon branch, including cerebellar cells."
        ),
    },
    "telencephalon excitatory neuron": {
        "cell_ontology_term_ids": ["CL:0000679"],
        "ontology_relation": "broader",
        "definition": "Glutamatergic neuron qualified to a telencephalon source branch.",
    },
    "telencephalon inhibitory neuron": {
        "cell_ontology_term_ids": ["CL:0000617"],
        "ontology_relation": "broader",
        "definition": "GABAergic neuron qualified to a telencephalon source branch.",
    },
    "vascular leptomeningeal cell": {
        "cell_ontology_term_ids": ["CL:4023051"],
        "ontology_relation": "exact",
        "definition": "Vascular leptomeningeal cell.",
    },
    "neuron": {
        "cell_ontology_term_ids": ["CL:0000540"],
        "ontology_relation": "exact",
        "definition": (
            "Prediction-only bridge for neuronal labels that lack the anatomical qualifier "
            "required by the 19-subclass Han taxonomy."
        ),
    },
    "Unassigned": {
        "cell_ontology_term_ids": [],
        "ontology_relation": "sentinel",
        "definition": "Missing, unsupported, or biologically ambiguous prediction.",
    },
}

PREDICTION_BRIDGE_LABELS = ("neuron",)
TARGET_LABELS = tuple(SOURCE_TO_TARGET.values()) + PREDICTION_BRIDGE_LABELS + ("Unassigned",)
CELL_ONTOLOGY_SHARED_FROM_PRIMARY = {
    "astrocyte": "astrocyte",
    "cerebral nuclei neuroblast": "forebrain neuroblast",
    "cholinergic/monoaminergic/peptidergic neuron": "neuron",
    "choroid plexus epithelial cell": "choroid plexus epithelial cell",
    "dentate gyrus granule cell": "neuron",
    "diencephalon/mesencephalon neuron": "neuron",
    "endothelial cell": "endothelial cell",
    "ependymal cell": "ependymal cell",
    "hypendymal cell": "hypendymal cell",
    "microglial cell": "microglial cell",
    "olfactory bulb excitatory neuron": "neuron",
    "olfactory bulb inhibitory neuron": "neuron",
    "olfactory ensheathing cell": "olfactory ensheathing cell",
    "oligodendrocyte precursor cell": "oligodendrocyte precursor cell",
    "oligodendrocyte": "oligodendrocyte",
    "rhombencephalon neuron": "neuron",
    "telencephalon excitatory neuron": "neuron",
    "telencephalon inhibitory neuron": "neuron",
    "vascular leptomeningeal cell": "vascular leptomeningeal cell",
    "neuron": "neuron",
    "Unassigned": "Unassigned",
}
CELL_ONTOLOGY_SHARED_TARGET_LABELS = (
    "astrocyte",
    "forebrain neuroblast",
    "neuron",
    "choroid plexus epithelial cell",
    "endothelial cell",
    "ependymal cell",
    "hypendymal cell",
    "microglial cell",
    "olfactory ensheathing cell",
    "oligodendrocyte precursor cell",
    "oligodendrocyte",
    "vascular leptomeningeal cell",
    "Unassigned",
)
CELL_ONTOLOGY_SHARED_DEFINITIONS = {
    label: TARGET_LABEL_DEFINITIONS[label]
    for label in CELL_ONTOLOGY_SHARED_TARGET_LABELS
    if label in TARGET_LABEL_DEFINITIONS
}
CELL_ONTOLOGY_SHARED_DEFINITIONS["forebrain neuroblast"] = {
    "cell_ontology_term_ids": ["CL:1000042"],
    "ontology_relation": "exact",
    "definition": "Forebrain neuroblast.",
}
CELL_ONTOLOGY_SHARED_DEFINITIONS["neuron"] = {
    "cell_ontology_term_ids": ["CL:0000540"],
    "ontology_relation": "exact",
    "definition": "Neuron; common collapse of neuronal truth branches and predictions.",
}
TRUTH_COLUMNS = (
    "section_id",
    "section_index",
    "bregma",
    "area_id",
    "cell_cluster_id",
    "cell_cluster",
    "cell_subclass",
    "cell_class",
)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return _digest(path, "sha256")


def _verify_public(path: Path, artifact: PublicArtifact) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required public atlas artifact is missing: {path}")
    if path.stat().st_size != artifact.size_bytes:
        raise ValueError(f"Size mismatch for {path.name}: {path.stat().st_size} bytes.")
    if _sha256(path) != artifact.sha256:
        raise ValueError(f"SHA-256 mismatch for public atlas artifact: {path.name}")


def _request_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {
        "User-Agent": "TissueAgent-cell-annotation-benchmark/1.0",
        **(headers or {}),
    }


def _download_public(artifact: PublicArtifact, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        _verify_public(destination, artifact)
        return
    temporary = destination.with_name(f".{destination.name}.partial")
    temporary.unlink(missing_ok=True)
    try:
        with requests.get(
            artifact.url,
            headers=_request_headers(),
            timeout=60,
            stream=True,
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as sink:
                for chunk in response.iter_content(chunk_size=8 * 1024**2):
                    sink.write(chunk)
        _verify_public(temporary, artifact)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _ensure_cell_ontology_snapshot(source_dir: Path) -> dict[str, Any]:
    destination = source_dir / "ontology" / CELL_ONTOLOGY_SNAPSHOT_FILENAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    _download_public(
        PublicArtifact(
            filename=CELL_ONTOLOGY_SNAPSHOT_FILENAME,
            size_bytes=CELL_ONTOLOGY_SNAPSHOT_SIZE_BYTES,
            sha256=CELL_ONTOLOGY_SNAPSHOT_SHA256,
            url=CELL_ONTOLOGY_SNAPSHOT_URL,
        ),
        destination,
        overwrite=False,
    )
    observed_names: dict[str, str] = {}
    current_id: str | None = None
    for line in destination.read_text(encoding="utf-8").splitlines():
        if line == "[Term]":
            current_id = None
        elif line.startswith("id: CL:"):
            current_id = line.removeprefix("id: ")
        elif current_id in CELL_ONTOLOGY_TERM_NAMES and line.startswith("name: "):
            observed_names[current_id] = line.removeprefix("name: ")
    if observed_names != CELL_ONTOLOGY_TERM_NAMES:
        missing = sorted(set(CELL_ONTOLOGY_TERM_NAMES).difference(observed_names))
        mismatched = sorted(
            ontology_id
            for ontology_id, expected_name in CELL_ONTOLOGY_TERM_NAMES.items()
            if ontology_id in observed_names and observed_names[ontology_id] != expected_name
        )
        raise ValueError(
            "Pinned Cell Ontology term validation failed: "
            f"missing={missing}, mismatched={mismatched}."
        )
    configured_ids = {
        ontology_id
        for definition in TARGET_LABEL_DEFINITIONS.values()
        for ontology_id in definition["cell_ontology_term_ids"]
    }
    if configured_ids != set(CELL_ONTOLOGY_TERM_NAMES):
        raise ValueError("Cell Ontology snapshot validation does not cover every configured ID.")
    return {
        "status": "verified",
        "path": _display_path(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "resolved_terms": observed_names,
    }


def _catalog_headers() -> dict[str, str]:
    return {
        "accessId": BDSC_ACCESS_ID,
        "appId": BDSC_APP_ID,
        "windowAppId": BDSC_APP_ID,
    }


def _download_catalog(destination: Path, *, overwrite: bool) -> dict[str, Any]:
    if destination.exists() and not overwrite:
        catalog = json.loads(destination.read_text(encoding="utf-8"))
        _validate_catalog(catalog)
        return catalog
    with requests.get(
        BDSC_CATALOG_URL,
        headers=_request_headers(_catalog_headers()),
        timeout=60,
    ) as response:
        response.raise_for_status()
        payload = response.json()
    if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise RuntimeError("The public BDSC catalog API did not return dataset metadata.")
    data = payload["data"]
    files = [
        {
            "id": str(item["id"]),
            "name": str(item["name"]),
            "size": int(item["size"]),
            "dir": str(item["dir"]),
        }
        for item in data.get("files", [])
    ]
    catalog = {
        "dataset_id": str(data.get("id")),
        "project_id": str(data.get("projectId")),
        "create_user": str(data.get("createUser")),
        "data_code": str(data.get("dataCode")),
        "title": str(data.get("dataTitleEn")),
        "data_jurisdiction": int(data.get("dataJurisdiction")),
        "files": sorted(files, key=lambda item: item["dir"]),
    }
    _validate_catalog(catalog)
    temporary = destination.with_name(f".{destination.name}.partial")
    temporary.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return catalog


def _expression_filename(section_id: str) -> str:
    return f"total_gene_{section_id}_mouse_f001_2D_mouse1-20230119.txt.gz"


def _validate_catalog(catalog: dict[str, Any]) -> None:
    expected_identity = {
        "dataset_id": BDSC_DATASET_ID,
        "project_id": BDSC_PROJECT_ID,
        "create_user": BDSC_CREATE_USER,
        "data_code": BDSC_DATA_CODE,
    }
    for key, expected in expected_identity.items():
        if catalog.get(key) != expected:
            raise ValueError(f"BDSC catalog {key} changed: {catalog.get(key)!r}.")
    files = catalog.get("files")
    if not isinstance(files, list) or len(files) != EXPECTED_CATALOG_FILES:
        raise ValueError("BDSC V2 catalog does not contain the expected 344 files.")
    expression = [
        item
        for item in files
        if "/total_gene_2D/mouse1-20230119/" in item["dir"] and item["name"].endswith(".txt.gz")
    ]
    if len(expression) != EXPECTED_MOUSE1_SECTIONS:
        raise ValueError("BDSC catalog does not contain 123 mouse1 2D expression files.")
    if sum(item["size"] for item in expression) != EXPECTED_MOUSE1_EXPRESSION_BYTES:
        raise ValueError("BDSC mouse1 2D expression byte total changed.")
    by_name = {item["name"]: item for item in expression}
    selected = []
    for section_id in SELECTED_SECTION_IDS:
        filename = _expression_filename(section_id)
        item = by_name.get(filename)
        if item is None or item["size"] != EXPRESSION_SIZES[section_id]:
            raise ValueError(f"Selected BDSC expression identity changed: {filename}")
        selected.append(item)
    if sum(item["size"] for item in selected) != EXPECTED_SELECTED_EXPRESSION_BYTES:
        raise ValueError("Selected BDSC expression byte total changed.")


def _load_types(path: Path) -> list[dict[str, Any]]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list) or len(values) != EXPECTED_CLUSTERS:
        raise ValueError("Atlas type table does not contain 308 clusters.")
    ids = [str(item.get("id")) for item in values]
    if len(ids) != len(set(ids)):
        raise ValueError("Atlas type table contains duplicate cluster IDs.")
    if sum(int(item.get("count", 0)) for item in values) != EXPECTED_ATLAS_CELLS:
        raise ValueError("Atlas type-table counts do not sum to 4,209,603 cells.")
    subclasses = {str(item.get("subclass")) for item in values}
    if subclasses != set(SOURCE_TO_TARGET):
        raise ValueError("Atlas publisher subclasses changed from the frozen 19-label set.")
    return values


def _load_samples(path: Path) -> dict[str, dict[str, Any]]:
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list) or len(samples) != 1:
        raise ValueError("Atlas samples response must contain one primary mouse.")
    if samples[0].get("sampleId") != "mouse_f001":
        raise ValueError("Atlas primary sample identity changed.")
    slices = samples[0].get("slices", [])
    if len(slices) != EXPECTED_MOUSE1_SECTIONS:
        raise ValueError("Atlas sample does not contain 123 coronal sections.")
    observed_panel = tuple(str(slices[index]["id"]) for index in SELECTED_SECTION_SOURCE_INDICES)
    if observed_panel != SELECTED_SECTION_IDS:
        raise ValueError("Atlas source-section order changed from the frozen evaluation panel.")
    by_id = {str(item["id"]): item for item in slices}
    if len(by_id) != len(slices) or not set(SELECTED_SECTION_IDS).issubset(by_id):
        raise ValueError("Atlas section IDs changed from the frozen evaluation panel.")
    return by_id


def download_public_metadata(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download fixed public catalog, taxonomy, section, and coordinate artifacts."""
    source_dir = Path(source_dir)
    public_dir = source_dir / "public_metadata"
    cell_dir = public_dir / "cells"
    cell_dir.mkdir(parents=True, exist_ok=True)
    catalog = _download_catalog(public_dir / "bdsc_v2_catalog.json", overwrite=overwrite)
    for artifact in PUBLIC_ARTIFACTS:
        _download_public(artifact, public_dir / artifact.filename, overwrite=overwrite)
    _load_types(public_dir / "atlas_cell_types.json")
    _load_samples(public_dir / "atlas_samples.json")

    section_artifacts = []
    for section_id in SELECTED_SECTION_IDS:
        size_bytes, sha256 = SECTION_ARTIFACTS[section_id]
        artifact = PublicArtifact(
            filename=f"{section_id}.json",
            size_bytes=size_bytes,
            sha256=sha256,
            url=f"{ATLAS_ROOT}/{section_id}.json",
        )
        _download_public(artifact, cell_dir / artifact.filename, overwrite=overwrite)
        section_artifacts.append(
            {
                "section_id": section_id,
                "path": _display_path(cell_dir / artifact.filename),
                "size_bytes": size_bytes,
                "sha256": sha256,
                "url": artifact.url,
            }
        )
    truth = _build_truth(public_dir)
    if len(truth) != EXPECTED_SELECTED_CELLS:
        raise ValueError("Selected public section metadata does not contain 478,740 cells.")
    if truth["cell_subclass"].nunique() != EXPECTED_SUBCLASSES:
        raise ValueError("Selected panel does not retain every frozen publisher subclass.")
    return {
        "status": "success",
        "source_dir": _display_path(source_dir),
        "catalog_path": _display_path(public_dir / "bdsc_v2_catalog.json"),
        "catalog_sha256": _sha256(public_dir / "bdsc_v2_catalog.json"),
        "catalog_files": len(catalog["files"]),
        "selected_sections": list(SELECTED_SECTION_IDS),
        "selected_cells": len(truth),
        "selected_subclasses": int(truth["cell_subclass"].nunique()),
        "section_artifacts": section_artifacts,
    }


def _read_token(token_file: str | Path | None) -> str:
    token = os.environ.get("BDSC_ACCESS_TOKEN", "").strip()
    if token_file is not None:
        if token:
            raise ValueError("Use either BDSC_ACCESS_TOKEN or --token-file, not both.")
        token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise PermissionError(
            "BDSC requires a registered-user download token. Set BDSC_ACCESS_TOKEN or pass "
            "--token-file; the token is read only in memory and is never persisted."
        )
    if any(character.isspace() or character == "/" for character in token):
        raise ValueError("BDSC token contains an invalid whitespace or path character.")
    return token


def _authenticated_url(relative_dir: str, filename: str, token: str) -> str:
    encoded_token = urllib.parse.quote(token, safe="")
    clean_dir = relative_dir.strip("/")
    directory = f"/{clean_dir}" if clean_dir else ""
    return f"{BDSC_RESOURCE_ROOT}{directory}/{encoded_token}/{filename}"


def _download_authenticated(
    *,
    relative_dir: str,
    filename: str,
    size_bytes: int,
    destination: Path,
    token: str,
    overwrite: bool,
) -> None:
    if destination.exists() and destination.stat().st_size == size_bytes and not overwrite:
        return
    temporary = destination.with_name(f".{destination.name}.partial")
    if overwrite:
        temporary.unlink(missing_ok=True)
    offset = temporary.stat().st_size if temporary.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    try:
        with requests.get(
            _authenticated_url(relative_dir, filename, token),
            headers=_request_headers(headers),
            timeout=120,
            stream=True,
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").partition(";")[0]
            if content_type == "application/json":
                raise PermissionError("BDSC rejected the registered-user download token.")
            if offset and response.status_code != 206:
                offset = 0
                temporary.unlink(missing_ok=True)
            mode = "ab" if offset else "wb"
            with temporary.open(mode) as sink:
                for chunk in response.iter_content(chunk_size=8 * 1024**2):
                    sink.write(chunk)
    except PermissionError:
        raise
    except (requests.RequestException, OSError):
        raise RuntimeError(
            f"Authenticated BDSC download failed for {filename}; the token-bearing URL "
            "was suppressed."
        ) from None
    if temporary.stat().st_size != size_bytes:
        raise ValueError(
            f"Incomplete BDSC download for {filename}: {temporary.stat().st_size} bytes."
        )
    temporary.replace(destination)


def _parse_md5_manifest(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 32:
            continue
        checksums[Path(parts[1].lstrip("*")).name] = parts[0].casefold()
    return checksums


def _validate_official_expression_md5(
    path: Path,
    checksums: dict[str, str],
) -> tuple[str, str]:
    compressed_expected = checksums.get(path.name)
    if compressed_expected is not None:
        observed = _digest(path, "md5")
        scope = "compressed_gzip"
        expected = compressed_expected
    else:
        uncompressed_name = path.name.removesuffix(".gz")
        expected = checksums.get(uncompressed_name)
        if expected is None:
            raise ValueError(f"Official MD5 manifest has no entry for {path.name}.")
        digest = hashlib.md5()
        with gzip.open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
                digest.update(chunk)
        observed = digest.hexdigest()
        scope = "decompressed_txt_payload"
    if observed != expected:
        raise ValueError(f"Official {scope} MD5 validation failed for {path.name}.")
    return expected, scope


def _validate_flat_annotation(
    path: Path,
    public_truth: pd.DataFrame,
) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size != FLAT_ANNOTATION_SIZE_BYTES:
        raise FileNotFoundError(f"Missing complete V2 flat annotation archive: {path}")
    selected = []
    columns = [
        "mouse",
        "section_id",
        "cell_id",
        "cell_cluster",
        "cell_subclass",
        "cell_class",
    ]
    for chunk in pd.read_csv(
        path,
        sep="\t",
        compression="gzip",
        usecols=columns,
        dtype={
            "mouse": "string",
            "section_id": "string",
            "cell_id": np.int64,
            "cell_cluster": "string",
            "cell_subclass": "string",
            "cell_class": "string",
        },
        chunksize=1_000_000,
    ):
        keep = (chunk["mouse"] == "mouse1") & chunk["section_id"].isin(SELECTED_SECTION_IDS)
        if keep.any():
            selected.append(chunk.loc[keep, columns[1:]])
    if not selected:
        raise ValueError("V2 flat annotation contains no cells from the frozen panel.")
    flat = pd.concat(selected, ignore_index=True)
    if flat.duplicated(["section_id", "cell_id"]).any():
        raise ValueError("V2 flat annotation has duplicate section/cell identifiers.")
    flat = flat.set_index(["section_id", "cell_id"])
    public_index = pd.MultiIndex.from_arrays(
        [public_truth["section_id"], public_truth["source_cell_id"]],
        names=["section_id", "cell_id"],
    )
    missing = public_index.difference(flat.index)
    if len(missing):
        raise ValueError(f"V2 flat annotation is missing {len(missing)} public evaluation cells.")
    aligned = flat.reindex(public_index)
    for column in ("cell_cluster", "cell_subclass", "cell_class"):
        expected = public_truth[column].astype(str).to_numpy()
        observed = aligned[column].astype(str).to_numpy()
        mismatches = int(np.count_nonzero(expected != observed))
        if mismatches:
            raise ValueError(
                f"V2 flat annotation disagrees with public {column} for {mismatches} cells."
            )
    return {
        "path": _display_path(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "selected_panel_rows": len(flat),
        "public_evaluation_rows_matched": len(public_truth),
        "additional_nonpublic_rows": len(flat) - len(public_truth),
        "exact_fields_matched": ["cell_cluster", "cell_subclass", "cell_class"],
    }


def _validate_expression_sources(source_dir: Path) -> list[dict[str, Any]]:
    md5_path = source_dir / "md5sum.txt"
    if not md5_path.exists() or md5_path.stat().st_size != 43_285:
        raise FileNotFoundError(f"Missing official BDSC checksum manifest: {md5_path}")
    checksums = _parse_md5_manifest(md5_path)
    expression_dir = source_dir / "expression"
    artifacts = []
    for section_id in SELECTED_SECTION_IDS:
        filename = _expression_filename(section_id)
        path = expression_dir / filename
        if not path.exists() or path.stat().st_size != EXPRESSION_SIZES[section_id]:
            raise FileNotFoundError(f"Missing complete expression source: {path}")
        expected_md5, md5_scope = _validate_official_expression_md5(path, checksums)
        artifacts.append(
            {
                "section_id": section_id,
                "path": path,
                "size_bytes": path.stat().st_size,
                "official_md5": expected_md5,
                "official_md5_scope": md5_scope,
            }
        )
    return artifacts


def download_expression_sources(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    *,
    token_file: str | Path | None = None,
    overwrite: bool = False,
    workers: int = 2,
) -> dict[str, Any]:
    """Download the frozen measured-expression panel from the registered-user release."""
    if workers < 1 or workers > 4:
        raise ValueError("workers must be between 1 and 4.")
    source_dir = Path(source_dir)
    download_public_metadata(source_dir)
    expression_dir = source_dir / "expression"
    expression_dir.mkdir(parents=True, exist_ok=True)
    md5_path = source_dir / "md5sum.txt"
    truth_path = source_dir / "stereoseq.celltypeTransfer.2mice.all.tsv.gz"
    required_downloads = [
        (md5_path, 43_285),
        (truth_path, FLAT_ANNOTATION_SIZE_BYTES),
        *[
            (expression_dir / _expression_filename(section_id), EXPRESSION_SIZES[section_id])
            for section_id in SELECTED_SECTION_IDS
        ],
    ]
    needs_authenticated_transfer = overwrite or any(
        not path.exists() or path.stat().st_size != expected_size
        for path, expected_size in required_downloads
    )
    token = _read_token(token_file) if needs_authenticated_transfer else ""
    _download_authenticated(
        relative_dir="",
        filename="md5sum.txt",
        size_bytes=43_285,
        destination=md5_path,
        token=token,
        overwrite=overwrite,
    )
    _download_authenticated(
        relative_dir="stereoseq/celltypeTransfer",
        filename=truth_path.name,
        size_bytes=FLAT_ANNOTATION_SIZE_BYTES,
        destination=truth_path,
        token=token,
        overwrite=overwrite,
    )
    checksums = _parse_md5_manifest(md5_path)

    def download_section(section_id: str) -> dict[str, Any]:
        filename = _expression_filename(section_id)
        destination = expression_dir / filename
        _download_authenticated(
            relative_dir="stereoseq/total_gene_2D/mouse1-20230119",
            filename=filename,
            size_bytes=EXPRESSION_SIZES[section_id],
            destination=destination,
            token=token,
            overwrite=overwrite,
        )
        expected_md5, md5_scope = _validate_official_expression_md5(
            destination,
            checksums,
        )
        return {
            "section_id": section_id,
            "path": _display_path(destination),
            "size_bytes": destination.stat().st_size,
            "sha256": _sha256(destination),
            "official_md5": expected_md5,
            "official_md5_scope": md5_scope,
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        artifacts = list(executor.map(download_section, SELECTED_SECTION_IDS))
    public_truth = _build_truth(source_dir / "public_metadata")
    flat_annotation = _validate_flat_annotation(truth_path, public_truth)
    legacy_manifest_md5 = checksums.get(truth_path.name)
    observed_compressed_md5 = _digest(truth_path, "md5")
    flat_annotation.update(
        {
            "legacy_manifest_md5": legacy_manifest_md5,
            "observed_compressed_md5": observed_compressed_md5,
            "legacy_manifest_md5_matches_v2_artifact": (
                legacy_manifest_md5 == observed_compressed_md5
            ),
            "validation_basis": (
                "V2 catalog size, complete gzip decoding, SHA-256, and exact public-cell "
                "cluster/subclass/class agreement; the legacy checksum entry names a different "
                "total_gene_2D/celltypeTransfer release path."
            ),
        }
    )
    return {
        "status": "success",
        "source_dir": _display_path(source_dir),
        "selected_sections": list(SELECTED_SECTION_IDS),
        "selected_expression_bytes": sum(item["size_bytes"] for item in artifacts),
        "expression_artifacts": artifacts,
        "flat_annotation": flat_annotation,
    }


def _build_truth(public_dir: Path) -> pd.DataFrame:
    type_by_id = {
        str(item["id"]): item for item in _load_types(public_dir / "atlas_cell_types.json")
    }
    samples = _load_samples(public_dir / "atlas_samples.json")
    frames = []
    for section_index, section_id in zip(
        SELECTED_SECTION_SOURCE_INDICES,
        SELECTED_SECTION_IDS,
        strict=True,
    ):
        cells = json.loads((public_dir / "cells" / f"{section_id}.json").read_text())
        if not isinstance(cells, list):
            raise ValueError(f"Atlas cell payload is not a list for {section_id}.")
        cell_ids = [int(item["id"]) for item in cells]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError(f"Atlas cell IDs are duplicated within {section_id}.")
        records = []
        for item in cells:
            type_id = str(item["type"])
            cell_type = type_by_id.get(type_id)
            if cell_type is None:
                raise ValueError(f"Unknown cell-cluster ID {type_id} in {section_id}.")
            cell_id = int(item["id"])
            records.append(
                {
                    "cell_id": f"mouse1:{section_id}:{cell_id}",
                    "source_cell_id": cell_id,
                    "x": float(item["x"]),
                    "y": float(item["y"]),
                    "section_id": section_id,
                    "section_index": section_index,
                    "bregma": float(samples[section_id]["bregma"]),
                    "area_id": str(item["area"]),
                    "cell_cluster_id": type_id,
                    "cell_cluster": str(cell_type["type"]),
                    "cell_subclass": str(cell_type["subclass"]),
                    "cell_class": str(cell_type["class"]),
                }
            )
        frames.append(pd.DataFrame.from_records(records))
    truth = pd.concat(frames, ignore_index=True)
    if truth["cell_id"].duplicated().any():
        raise ValueError("Panel observation identifiers are not globally unique.")
    return truth.set_index("cell_id", drop=True)


def _build_section_matrix(
    expression_path: Path,
    section_truth: pd.DataFrame,
    gene_to_column: dict[str, int],
    *,
    chunk_rows: int,
) -> tuple[sparse.csr_matrix, dict[str, Any]]:
    if chunk_rows < 1:
        raise ValueError("chunk_rows must be positive.")
    cell_to_row = {int(cell_id): row for row, cell_id in enumerate(section_truth["source_cell_id"])}
    row_blocks: list[np.ndarray] = []
    column_blocks: list[np.ndarray] = []
    data_blocks: list[np.ndarray] = []
    source_rows = 0
    retained_rows = 0
    for chunk in pd.read_csv(
        expression_path,
        sep="\t",
        compression="gzip",
        usecols=["gene", "umi_count", "cell_label"],
        dtype={"gene": "string", "umi_count": np.int64, "cell_label": np.int64},
        chunksize=chunk_rows,
    ):
        source_rows += len(chunk)
        rows = chunk["cell_label"].map(cell_to_row)
        keep = rows.notna()
        if not keep.any():
            continue
        retained = chunk.loc[keep, ["gene", "umi_count"]].copy()
        retained["row"] = rows.loc[keep].to_numpy(dtype=np.int32)
        if retained["gene"].isna().any() or (retained["umi_count"] <= 0).any():
            raise ValueError(f"Invalid measured expression values in {expression_path.name}.")
        grouped = retained.groupby(["row", "gene"], sort=False, observed=True)["umi_count"].sum()
        grouped = grouped.reset_index()
        for gene in pd.unique(grouped["gene"].astype(str)):
            if gene not in gene_to_column:
                gene_to_column[gene] = len(gene_to_column)
        row_blocks.append(grouped["row"].to_numpy(dtype=np.int32))
        column_blocks.append(
            grouped["gene"].astype(str).map(gene_to_column).to_numpy(dtype=np.int32)
        )
        data_blocks.append(grouped["umi_count"].to_numpy(dtype=np.float32))
        retained_rows += int(keep.sum())
    if not data_blocks:
        raise ValueError(f"No selected cells were found in {expression_path.name}.")
    matrix = sparse.coo_matrix(
        (
            np.concatenate(data_blocks),
            (np.concatenate(row_blocks), np.concatenate(column_blocks)),
        ),
        shape=(len(section_truth), len(gene_to_column)),
        dtype=np.float32,
    ).tocsr()
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    cells_without_counts = int(np.count_nonzero(np.asarray(matrix.sum(axis=1)).ravel() == 0))
    if cells_without_counts:
        raise ValueError(
            f"{cells_without_counts} selected cells have no measured counts in "
            f"{expression_path.name}."
        )
    return matrix, {
        "source_dnb_rows": source_rows,
        "retained_dnb_rows": retained_rows,
        "n_nonzero": int(matrix.nnz),
        "n_cells": int(matrix.shape[0]),
    }


def _validate_prepared(query_path: Path, truth_path: Path) -> dict[str, Any]:
    query = ad.read_h5ad(query_path, backed="r")
    try:
        if query.n_obs != EXPECTED_SELECTED_CELLS or query.n_vars <= 0:
            raise ValueError(f"Unexpected prepared Stereo-seq shape: {query.shape}.")
        if len(query.obs.columns):
            raise ValueError("Prepared Stereo-seq query .obs must be label-free and empty.")
        if len(query.var.columns):
            raise ValueError("Prepared Stereo-seq query .var must not expose source annotations.")
        if tuple(query.obsm.keys()) != ("spatial",):
            raise ValueError("Prepared query must contain only obsm['spatial'].")
        if query.obsm["spatial"].shape != (query.n_obs, 3):
            raise ValueError("Prepared spatial coordinates must contain x, y, and bregma.")
        coordinates = np.asarray(query.obsm["spatial"])
        if not np.isfinite(coordinates).all():
            raise ValueError("Prepared spatial coordinates contain non-finite values.")
        if query.layers or query.obsp or query.uns or query.raw is not None:
            raise ValueError("Prepared query contains forbidden derived analysis artifacts.")
        sample_rows = np.unique(
            np.linspace(0, query.n_obs - 1, min(query.n_obs, 2_048), dtype=np.int64)
        )
        sampled_matrix = query.X[sample_rows]
        sampled_values = (
            sampled_matrix.data
            if sparse.issparse(sampled_matrix)
            else np.asarray(sampled_matrix).ravel()
        )
        if not np.isfinite(sampled_values).all() or (sampled_values < 0).any():
            raise ValueError("Prepared expression contains negative or non-finite values.")
        if not np.allclose(sampled_values, np.rint(sampled_values), atol=1e-6, rtol=0):
            raise ValueError("Prepared expression is not raw UMI-count-like.")
        query_ids = pd.Index(query.obs_names.astype(str), name="cell_id")
        gene_names = pd.Index(query.var_names.astype(str))
        if not query_ids.is_unique or not gene_names.is_unique:
            raise ValueError("Prepared query identifiers are not unique.")
    finally:
        query.file.close()
    truth = pd.read_csv(truth_path, sep="\t", dtype={"cell_id": str}).set_index("cell_id")
    if not truth.index.equals(query_ids):
        raise ValueError("Ground-truth sidecar does not preserve exact query observation order.")
    if tuple(truth.columns) != TRUTH_COLUMNS:
        raise ValueError(f"Unexpected Stereo-seq truth columns: {list(truth.columns)}.")
    if set(truth["cell_subclass"]) != set(SOURCE_TO_TARGET):
        raise ValueError("Ground-truth sidecar does not contain the frozen 19 subclasses.")
    return {
        "n_obs": len(query_ids),
        "n_vars": len(gene_names),
        "n_sections": int(truth["section_id"].nunique()),
        "n_ground_truth_subclasses": int(truth["cell_subclass"].nunique()),
    }


def build_han_mouse_brain_stereoseq_benchmark(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output: str | Path = DEFAULT_OUTPUT,
    *,
    overwrite: bool = False,
    chunk_rows: int = 2_000_000,
) -> dict[str, Any]:
    """Aggregate measured DNB counts into a sparse, cell-level, label-free query."""
    source_dir = Path(source_dir)
    output = Path(output)
    truth_path = output.with_suffix(".ground_truth.tsv")
    provenance_path = output.with_suffix(".preparation.json")
    existing = [path for path in (output, truth_path, provenance_path) if path.exists()]
    if existing and not overwrite:
        if len(existing) != 3:
            raise FileExistsError("Prepared Stereo-seq artifacts are incomplete.")
        validation = _validate_prepared(output, truth_path)
        prior = json.loads(provenance_path.read_text(encoding="utf-8"))
        if prior.get("query_sha256") != _sha256(output):
            raise ValueError("Prepared Stereo-seq SHA-256 does not match its provenance.")
        if prior.get("ground_truth_sha256") != _sha256(truth_path):
            raise ValueError("Stereo-seq truth SHA-256 does not match its provenance.")
        return {**prior, **validation, "status": "existing"}

    public_dir = source_dir / "public_metadata"
    download_public_metadata(source_dir)
    truth_with_source = _build_truth(public_dir)
    flat_annotation_audit = _validate_flat_annotation(
        source_dir / "stereoseq.celltypeTransfer.2mice.all.tsv.gz",
        truth_with_source,
    )
    validated_expression_sources = _validate_expression_sources(source_dir)
    expression_dir = source_dir / "expression"

    output.parent.mkdir(parents=True, exist_ok=True)
    gene_to_column: dict[str, int] = {}
    section_audits = []
    matrix_paths = []
    with tempfile.TemporaryDirectory(prefix="stereoseq-build-", dir=output.parent) as temporary:
        temporary_dir = Path(temporary)
        for section_id in SELECTED_SECTION_IDS:
            section_truth = truth_with_source[truth_with_source["section_id"] == section_id]
            expression_path = expression_dir / _expression_filename(section_id)
            matrix, audit = _build_section_matrix(
                expression_path,
                section_truth,
                gene_to_column,
                chunk_rows=chunk_rows,
            )
            matrix_path = temporary_dir / f"{section_id}.npz"
            sparse.save_npz(matrix_path, matrix, compressed=True)
            matrix_paths.append(matrix_path)
            section_audits.append({"section_id": section_id, **audit})

        n_genes = len(gene_to_column)
        blocks = []
        for matrix_path in matrix_paths:
            matrix = sparse.load_npz(matrix_path)
            if matrix.shape[1] < n_genes:
                matrix = sparse.hstack(
                    [
                        matrix,
                        sparse.csr_matrix((matrix.shape[0], n_genes - matrix.shape[1])),
                    ],
                    format="csr",
                )
            blocks.append(matrix)
        combined = sparse.vstack(blocks, format="csr")

    sorted_genes = sorted(gene_to_column)
    permutation = np.asarray([gene_to_column[gene] for gene in sorted_genes], dtype=np.int64)
    combined = combined[:, permutation]
    query_ids = pd.Index(truth_with_source.index.astype(str), name="cell_id")
    query = ad.AnnData(
        X=combined,
        obs=pd.DataFrame(index=query_ids),
        var=pd.DataFrame(index=pd.Index(sorted_genes, name="gene_symbol")),
    )
    query.obsm["spatial"] = truth_with_source[["x", "y", "bregma"]].to_numpy(dtype=np.float32)
    truth = truth_with_source[list(TRUTH_COLUMNS)].copy()

    query_temporary = output.with_name(f".{output.stem}.partial.h5ad")
    truth_temporary = truth_path.with_name(f".{truth_path.name}.partial")
    provenance_temporary = provenance_path.with_name(f".{provenance_path.name}.partial")
    for path in (query_temporary, truth_temporary, provenance_temporary):
        path.unlink(missing_ok=True)
    try:
        query.write_h5ad(query_temporary, compression="gzip")
        truth.to_csv(truth_temporary, sep="\t", index=True)
        validation = _validate_prepared(query_temporary, truth_temporary)
        expression_sources = []
        for artifact in validated_expression_sources:
            section_id = artifact["section_id"]
            path = artifact["path"]
            expression_sources.append(
                {
                    "section_id": section_id,
                    "path": _display_path(path),
                    "size_bytes": artifact["size_bytes"],
                    "sha256": _sha256(path),
                    "official_md5": artifact["official_md5"],
                    "official_md5_scope": artifact["official_md5_scope"],
                }
            )
        public_metadata_sources = [
            {
                "kind": "bdsc_catalog",
                "path": _display_path(public_dir / "bdsc_v2_catalog.json"),
                "sha256": _sha256(public_dir / "bdsc_v2_catalog.json"),
                "url": BDSC_CATALOG_URL,
            },
            *[
                {
                    "kind": "atlas_metadata",
                    "path": _display_path(public_dir / artifact.filename),
                    "size_bytes": artifact.size_bytes,
                    "sha256": artifact.sha256,
                    "url": artifact.url,
                }
                for artifact in PUBLIC_ARTIFACTS
            ],
            *[
                {
                    "kind": "atlas_section_cells",
                    "section_id": section_id,
                    "path": _display_path(public_dir / "cells" / f"{section_id}.json"),
                    "size_bytes": SECTION_ARTIFACTS[section_id][0],
                    "sha256": SECTION_ARTIFACTS[section_id][1],
                    "url": f"{ATLAS_ROOT}/{section_id}.json",
                }
                for section_id in SELECTED_SECTION_IDS
            ],
        ]
        result = {
            "status": "success",
            "operation": "prepare_han_mouse_brain_stereoseq_benchmark",
            "dataset_id": DATASET_ID,
            "output_path": _display_path(output),
            "ground_truth_path": _display_path(truth_path),
            **validation,
            "cohort_definition": (
                "All 478,740 high-quality Spatial-ID-annotated cells in a frozen 15-section "
                "panel sampled across the full anterior-posterior extent of mouse1."
            ),
            "panel_selection": {
                "method": "evenly_spaced_section_indices_before_method_execution",
                "source_section_count": EXPECTED_MOUSE1_SECTIONS,
                "selected_section_ids": list(SELECTED_SECTION_IDS),
                "retains_all_publisher_subclasses": True,
                "method_predictions_used": False,
            },
            "query_contents": {
                "matrix_kind": "raw_umi_counts_aggregated_from_measured_dnbs",
                "obs_columns": [],
                "var_names": "gene_symbol",
                "var_columns": [],
                "obsm_keys": ["spatial"],
                "spatial_axes": ["x", "y", "bregma"],
                "uns_keys": [],
            },
            "truth_join": "exact_mouse_section_cell_id",
            "section_audits": section_audits,
            "expression_sources": expression_sources,
            "public_metadata_sources": public_metadata_sources,
            "flat_annotation_audit": flat_annotation_audit,
            "query_sha256": _sha256(query_temporary),
            "ground_truth_sha256": _sha256(truth_temporary),
            "annotation_truth_caveat": (
                "The 19 subclasses are Spatial-ID transfers from the matched Han snRNA-seq "
                "taxonomy, not orthogonally measured cell identities."
            ),
            "independence_scope": (
                "The pinned Harmony reference and CellTypist model contain no known Han "
                "Stereo-seq observations, but GPT training-data inclusion cannot be certified; "
                "the truth taxonomy and external models also share some Zeisel/Allen/Yao lineage."
            ),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        provenance_temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        query_temporary.replace(output)
        truth_temporary.replace(truth_path)
        provenance_temporary.replace(provenance_path)
    except Exception:
        query_temporary.unlink(missing_ok=True)
        truth_temporary.unlink(missing_ok=True)
        provenance_temporary.unlink(missing_ok=True)
        raise
    return result


def build_initial_label_contract(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output: str | Path = DEFAULT_MAPPING_OUTPUT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Freeze the Han taxonomy and ontology-shared headline target space."""
    source_dir = Path(source_dir)
    output = Path(output)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Label contract already exists: {output}")
    download_public_metadata(source_dir)
    ontology_validation = _ensure_cell_ontology_snapshot(source_dir)
    truth = _build_truth(source_dir / "public_metadata")
    harmonized = truth["cell_subclass"].map(SOURCE_TO_TARGET)
    if harmonized.isna().any() or set(harmonized) != set(SOURCE_TO_TARGET.values()):
        raise ValueError("Frozen ground-truth mapping is incomplete.")
    counts = {
        label: int(count)
        for label, count in harmonized.value_counts().reindex(TARGET_LABELS, fill_value=0).items()
    }
    payload = {
        "mapping_version": "han_mouse_brain_stereoseq_subclass_v2",
        "prediction_mapping_status": "pending",
        "ontology": {
            "name": "Cell Ontology",
            "release": "2026-06-08",
            "version_iri": CELL_ONTOLOGY_SNAPSHOT_URL,
            "snapshot_sha256": CELL_ONTOLOGY_SNAPSHOT_SHA256,
            "term_resolution_evidence": ontology_validation,
            "composite_policy": (
                "Preserve all publisher subclasses; dataset-defined anatomical neuronal groups "
                "use broader CL anchors in the fine taxonomy. The headline ontology-shared "
                "space collapses those anatomical branches to CL:0000540 neuron."
            ),
        },
        "target_label_definition": {
            "source_column": "cell_subclass",
            "source_hierarchy_context": "cell_class and cell_cluster",
            "method_predictions_used": False,
            "resolution": "All 19 Han Spatial-ID publisher subclasses plus one prediction bridge",
            "frozen_before_method_mapping": True,
        },
        "target_labels": list(TARGET_LABELS),
        "target_label_definitions": TARGET_LABEL_DEFINITIONS,
        "prediction_only_targets": list(PREDICTION_BRIDGE_LABELS),
        "prediction_only_target_scope": "primary fine-taxonomy space only",
        "ground_truth_mapping": SOURCE_TO_TARGET,
        "ground_truth_target_counts": counts,
        "primary_metric": "macro_f1 on cell_ontology_shared",
        "headline_label_space": "cell_ontology_shared",
        "secondary_label_spaces": {
            "cell_ontology_shared": {
                "purpose": (
                    "Headline shared cell-type space; anatomical neuron branches are not scored "
                    "as distinct cell types."
                ),
                "target_labels": list(CELL_ONTOLOGY_SHARED_TARGET_LABELS),
                "target_label_definitions": CELL_ONTOLOGY_SHARED_DEFINITIONS,
                "mapping_from_primary": CELL_ONTOLOGY_SHARED_FROM_PRIMARY,
            }
        },
        "evaluation_notes": [
            "The 19-subclass section panel and target biology were frozen before inference; "
            "the ontology-shared collapse is deterministic and prediction-independent.",
            "Every selected cell must receive a prediction and remain in exact query order.",
            "Generic neuronal predictions map to the prediction-only neuron bridge and are "
            "scorable in cell_ontology_shared without inventing an anatomical branch.",
            "Accuracy and macro precision are reported with section-grouped uncertainty.",
            "Spatial-ID truth is a computational transfer from matched snRNA-seq and is scored "
            "as concordance with the Han taxonomy rather than absolute biological ground truth.",
        ],
        "primary_excluded_ground_truth_labels": [],
        "common_prediction_mapping": {},
        "method_prediction_mapping": {
            "tissueagent": {},
            "celltypist": {},
            "gptcelltype": {},
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.partial")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {
        "status": "success",
        "output_path": _display_path(output),
        "mapping_version": payload["mapping_version"],
        "n_ground_truth_labels": len(SOURCE_TO_TARGET),
        "n_target_labels": len(TARGET_LABELS),
        "ground_truth_target_counts": counts,
        "method_predictions_used": False,
    }


def write_benchmark_manifest(
    query_path: str | Path = DEFAULT_OUTPUT,
    mapping_path: str | Path = DEFAULT_MAPPING_OUTPUT,
    output: str | Path = DEFAULT_MANIFEST_OUTPUT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write the immutable manifest consumed by the generic benchmark runners."""
    query_path = Path(query_path)
    truth_path = query_path.with_suffix(".ground_truth.tsv")
    mapping_path = Path(mapping_path)
    output = Path(output)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Benchmark manifest already exists: {output}")
    validation = _validate_prepared(query_path, truth_path)
    if not mapping_path.exists():
        raise FileNotFoundError(f"Frozen label contract is missing: {mapping_path}")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if mapping.get("prediction_mapping_status") != "pending":
        raise ValueError("Manifest creation requires the pre-inference pending label contract.")
    if mapping.get("target_labels") != list(TARGET_LABELS):
        raise ValueError("Frozen target labels do not match the Stereo-seq preparation script.")
    if mapping.get("ground_truth_mapping") != SOURCE_TO_TARGET:
        raise ValueError("Frozen ground-truth mapping changed before manifest creation.")
    method_mappings = mapping.get("method_prediction_mapping", {})
    if any(method_mappings.get(method) for method in ("tissueagent", "celltypist", "gptcelltype")):
        raise ValueError("Pre-inference label contract already contains prediction mappings.")
    if mapping.get("common_prediction_mapping"):
        raise ValueError("Pre-inference label contract already contains a common crosswalk.")
    if any(mapping.get("method_prediction_rules", {}).values()):
        raise ValueError("Pre-inference label contract already contains prediction rules.")
    label_contract_sha256 = _label_contract_sha256(mapping)

    pinned_files = (
        (REFERENCE_PATH, REFERENCE_SIZE_BYTES, REFERENCE_SHA256, "reference"),
        (
            CELLTYPIST_MODEL_PATH,
            CELLTYPIST_MODEL_SIZE_BYTES,
            CELLTYPIST_MODEL_SHA256,
            "CellTypist model",
        ),
    )
    for path, expected_size, expected_sha256, description in pinned_files:
        if not path.exists() or path.stat().st_size != expected_size:
            raise FileNotFoundError(
                f"Pinned {description} is missing or has the wrong size: {path}"
            )
        if _sha256(path) != expected_sha256:
            raise ValueError(f"Pinned {description} SHA-256 changed: {path}")

    payload = {
        "schema_version": "1.0",
        "dataset_id": DATASET_ID,
        "label_contract_sha256": label_contract_sha256,
        "require_pending_label_mapping": True,
        "title": "Han whole adult mouse-brain Stereo-seq 15-section evaluation panel",
        "species": "mouse",
        "tissue": "whole adult mouse brain",
        "disease": "normal",
        "developmental_stage": "11-week adult",
        "source": {
            "publication_doi": "10.1016/j.neuron.2025.02.015",
            "bdsc_doi": "10.12412/BSDC.1699433096.20001",
            "bdsc_dataset_id": BDSC_DATASET_ID,
            "mouse": "mouse_f001",
            "cohort": (
                "All 478,740 annotated cells in 15 sections frozen at source indices "
                "0,9,17,26,35,44,52,61,70,78,87,96,105,113,122."
            ),
            "note": (
                "Spatial-ID annotations are transfers from the matched Han snRNA-seq taxonomy; "
                "they are not orthogonally measured identities."
            ),
        },
        "query": {
            "kind": "local_h5ad",
            "path": _display_path(query_path),
            "expected_n_obs": validation["n_obs"],
            "expected_n_vars": validation["n_vars"],
            "size_bytes": query_path.stat().st_size,
            "sha256": _sha256(query_path),
            "require_spatial": True,
            "selection_blind_allowed_metadata": {
                "obs": [],
                "obsm": ["spatial"],
                "obsp": [],
                "uns": [],
            },
            "blinding_threat_model": (
                "The blinded query contains no annotation metadata and uses an opaque run path. "
                "Exact public observation identifiers and coordinates are retained for source "
                "auditability, so deliberate re-identification against the public atlas is out "
                "of scope and prohibited by the benchmark prompt."
            ),
        },
        "ground_truth": {
            "column": "cell_subclass",
            "held_out_columns": ["cell_subclass"],
            "path": _display_path(truth_path),
            "sha256": _sha256(truth_path),
            "grouped_bootstrap_column": "section_id",
            "note": "Score concordance with the publisher's 19-subclass Spatial-ID taxonomy.",
        },
        "reference": {
            "kind": "local_h5ad",
            "path": _display_path(REFERENCE_PATH),
            "size_bytes": REFERENCE_SIZE_BYTES,
            "sha256": REFERENCE_SHA256,
            "cell_type_column": "cell_type",
            "known_source_dataset_ids": [
                "d7291f04-fbbb-4d65-990a-f01fa44e915b",
                "e0ed3c55-aff6-4bb7-b6ff-98a2d90b890c",
                "dbb4e1ed-d820-4e83-981f-88ef7eb55a35",
                "3bbb6cf9-72b9-41be-b568-656de6eb18b5",
            ],
            "forbidden_sources": [
                "Han Stereo-seq expression observations",
                "mouseBrain.snRNAseq.308Clusters.seurat.20241021.rds",
            ],
            "note": (
                "Pinned pre-existing CELLxGENE reference; exact query/reference observation-ID "
                "overlap must be zero. It contains no known Han observations, but shares some "
                "Allen/Zeisel taxonomy lineage with the transferred truth."
            ),
        },
        "tissueagent": {
            "min_cells": 10,
            "n_pcs": 30,
            "min_shared_genes": 500,
            "harmony_max_iter": 20,
            "classifier": "mlp",
            "preserve_all_spatial_obs": True,
        },
        "celltypist": {
            "mode": "builtin",
            "model": CELLTYPIST_MODEL_PATH.name,
            "model_size_bytes": CELLTYPIST_MODEL_SIZE_BYTES,
            "model_sha256": CELLTYPIST_MODEL_SHA256,
            "training_source_doi": "10.1038/s41586-023-06812-z",
        },
        "gptcelltype": {
            "tissue_name": "whole adult mouse brain",
            "species_name": "mouse",
            "model": "gpt-5.1",
            "max_marker_cells_per_cluster": 500,
            "max_marker_cells_total": 50_000,
            "marker_sampling_random_seed": 42,
            "training_data_independence": "not_certifiable",
        },
        "mapping": _display_path(mapping_path),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.partial")
    temporary.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    temporary.replace(output)
    return {
        "status": "success",
        "output_path": _display_path(output),
        "query_sha256": payload["query"]["sha256"],
        "ground_truth_sha256": payload["ground_truth"]["sha256"],
        "reference_sha256": REFERENCE_SHA256,
        "celltypist_model_sha256": CELLTYPIST_MODEL_SHA256,
        "label_contract_sha256": label_contract_sha256,
        "n_obs": validation["n_obs"],
        "n_vars": validation["n_vars"],
    }


def main() -> None:
    """Run the reproducible Han Stereo-seq preparation commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["metadata", "download", "build", "mapping", "manifest", "prepare"],
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mapping-output", type=Path, default=DEFAULT_MAPPING_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--chunk-rows", type=int, default=2_000_000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.command == "metadata":
        result = download_public_metadata(args.source_dir, overwrite=args.overwrite)
    elif args.command == "download":
        result = download_expression_sources(
            args.source_dir,
            token_file=args.token_file,
            overwrite=args.overwrite,
            workers=args.workers,
        )
    elif args.command == "build":
        result = build_han_mouse_brain_stereoseq_benchmark(
            args.source_dir,
            args.output,
            overwrite=args.overwrite,
            chunk_rows=args.chunk_rows,
        )
    elif args.command == "mapping":
        result = build_initial_label_contract(
            args.source_dir,
            args.mapping_output,
            overwrite=args.overwrite,
        )
    elif args.command == "manifest":
        result = write_benchmark_manifest(
            args.output,
            args.mapping_output,
            args.manifest_output,
            overwrite=args.overwrite,
        )
    else:
        download_expression_sources(
            args.source_dir,
            token_file=args.token_file,
            overwrite=args.overwrite,
            workers=args.workers,
        )
        preparation = build_han_mouse_brain_stereoseq_benchmark(
            args.source_dir,
            args.output,
            overwrite=args.overwrite,
            chunk_rows=args.chunk_rows,
        )
        if args.mapping_output.exists():
            mapping = {
                "status": "existing",
                "output_path": _display_path(args.mapping_output),
            }
        else:
            mapping = build_initial_label_contract(
                args.source_dir,
                args.mapping_output,
            )
        manifest = write_benchmark_manifest(
            args.output,
            args.mapping_output,
            args.manifest_output,
            overwrite=args.overwrite,
        )
        result = {
            "status": "success",
            "preparation": preparation,
            "mapping": mapping,
            "manifest": manifest,
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
