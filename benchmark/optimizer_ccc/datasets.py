"""Pinned dataset manifest for the optimizer CCC benchmark.

Every benchmark round — agent runs and the expert reference alike — consumes
the SAME pre-staged, labeled, single-section inputs built by
``prepare_inputs.py``. Pinning inputs (section, label column, label derivation)
keeps input divergence out of the accuracy signal: any Spearman/Jaccard delta
between rounds is then attributable to the knowledge layer, not to the agent
subsetting or clustering differently than the reference did.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DATASETS_DIR = REPO_ROOT / "workspace" / "library" / "datasets"
BENCH_DIR = REPO_ROOT / "benchmark" / "optimizer_ccc"
REFERENCE_DIR = BENCH_DIR / "reference"

# Shared ccc_data_prep.py arguments (script defaults, pinned explicitly).
PREP_ARGS = {"crop_n": 2000, "max_pairs": 50, "knn_k": 6}
SEED = 1337

DATASETS: dict[str, dict] = {
    "lymph_node": {
        # Human lymph-node Visium; ships with NO labels, so prepare_inputs.py
        # derives spatial domains once (KMeans k=8 on 30 PCs, seed pinned) and
        # bakes them in — both agent and reference read the same labels.
        "raw": "lymph_node_visium.h5ad",
        "staged": "opt_ccc_lymph_node.h5ad",
        "species": "human",
        "cell_type": "domain",
        "platform": "10x Visium (sequencing spots)",
    },
    "dlpfc": {
        # Human DLPFC Visium, section 151673 of the 12-section Maynard set,
        # manual laminar annotations in layer_guess_reordered (staged as 'layer').
        "raw": "dlpfc_visium.h5ad",
        "staged": "opt_ccc_dlpfc_151673.h5ad",
        "species": "human",
        "cell_type": "layer",
        "platform": "10x Visium (sequencing spots)",
        "section": {"sample_name": "151673"},
    },
    "merfish": {
        # Mouse hypothalamus MERFISH, single section pinned to the same
        # (Animal_ID, Bregma) the archived successful agent run used.
        "raw": "merfish_hypothalamus.h5ad",
        "staged": "opt_ccc_merfish.h5ad",
        "species": "mouse",
        "cell_type": "Cell_class",
        "platform": "MERFISH (single-cell imaging)",
        "section": {"Animal_ID": 1, "Bregma": -0.14},
    },
}


def staged_path(name: str) -> Path:
    return RAW_DATASETS_DIR / DATASETS[name]["staged"]


def agent_prompt(name: str) -> str:
    """The fixed benchmark prompt for one dataset.

    Deliberately lean: it pins the input facts (file, species, label column)
    but carries no method knowledge — the workflow itself must come from the
    plan template and skills, which is what the optimizer is improving.
    """
    d = DATASETS[name]
    return (
        f"Run the four-member ensemble cell-cell communication analysis "
        f"(LIANA+, COMMOT, stLearn, decoupler) on library/datasets/{d['staged']}. "
        f"The file is a single {d['platform']} section, species {d['species']}, "
        f"gene symbols, with cell-type/domain labels in obs['{d['cell_type']}'] "
        f"and native-unit coordinates in obsm['spatial']. "
        f"Produce project/outputs/ccc_ensemble.csv, one ranked row per "
        f"ligand-receptor pair."
    )
