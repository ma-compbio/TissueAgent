"""Build an anonymized Farah dataset for the label-leakage control experiment.

Source: `demo/data/dataset_farah_heart_merfish.h5ad` (228k cells × 238 genes).

The original `Populations` column contains label names that leak the
target community. Most damaging: `ncCM-AVC-like` literally spells out
"AVC" (the recovery target region). Less damaging but still suggestive:
`vCM-LV-AV`, `vCM-RV-AV`, `ncCM-IFT-like`.

We replace every population label with a systematic alphanumeric code so
the agent cannot identify the AVC-restricted subtype by name alone. The
mapping is saved to `farah_anon_label_map.json` so we can interpret
agent output back to original labels.

Run:
    conda run -n tissueagent --live-stream python demo/build_farah_anon_h5ad.py
"""

from __future__ import annotations

import json
from pathlib import Path

import anndata as ad

_IN = Path(__file__).resolve().parent / "data" / "dataset_farah_heart_merfish.h5ad"
_OUT = Path(__file__).resolve().parent / "data" / "dataset_farah_anon.h5ad"
_LABEL_MAP_PATH = Path(__file__).resolve().parent / "data" / "farah_anon_label_map.json"


def main() -> None:
    if not _IN.is_file():
        raise SystemExit(f"Source missing: {_IN}")

    print(f"Loading {_IN} …")
    adata = ad.read_h5ad(_IN)
    print(f"  shape: {adata.shape}")
    print(f"  obs cols: {list(adata.obs.columns)}")

    populations = adata.obs["Populations"].astype(str)
    unique = sorted(populations.unique())
    print(f"  unique Populations: {len(unique)}")

    # Assign systematic codes A, B, C, ... preserving original size order
    # (largest first → A) so a downstream analyst can re-derive without the
    # map if needed. Codes are *biology-free* short strings; they do NOT
    # encode any anatomical or cell-type information.
    size_order = (
        populations.value_counts().sort_values(ascending=False).index.tolist()
    )
    code_map: dict[str, str] = {}
    for i, label in enumerate(size_order):
        # Use a 2-char code so larger panels don't run out
        if i < 26:
            code = f"P{chr(ord('A') + i)}"  # PA, PB, PC, ...
        else:
            code = f"P{chr(ord('A') + i // 26 - 1)}{chr(ord('A') + i % 26)}"
        code_map[label] = code

    adata.obs["Populations_original"] = populations.values  # keep for our own forensics
    adata.obs["Populations"] = populations.map(code_map).astype("category")
    # Move the original column out of the way - the recovery agent should
    # not see the original labels. We'll DROP this column before writing.
    adata.obs = adata.obs.drop(columns=["Populations_original"])

    # Update the dataset_provenance to record the anonymization.
    prov = dict(adata.uns.get("dataset_provenance", {}))
    prov["anonymized_for_label_leakage_control"] = True
    prov["label_map_file"] = str(_LABEL_MAP_PATH.name)
    adata.uns["dataset_provenance"] = prov

    print(f"\nMapping (original → anon code):")
    for original, code in sorted(code_map.items(), key=lambda kv: kv[0]):
        n_cells = (populations == original).sum()
        marker = "  <-- recovery target" if "AVC" in original else ""
        print(f"  {original:25s} → {code}  (n={n_cells:>6d}){marker}")

    _LABEL_MAP_PATH.write_text(json.dumps(code_map, indent=2), encoding="utf-8")
    print(f"\nSaved label map: {_LABEL_MAP_PATH}")

    print(f"Writing {_OUT} …")
    adata.write_h5ad(_OUT, compression="gzip")
    print(f"  size: {_OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
