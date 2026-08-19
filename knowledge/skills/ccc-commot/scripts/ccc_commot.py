"""CCC ensemble — Step 3: COMMOT spatial_communication (spatial OT axis).

Directly runnable AND importable. Run the whole step in the kernel with:

    %run project/skills/ccc-commot/scripts/ccc_commot.py

(this installs the `commot` PyPI package if needed, then scores) or import the
scorer and call it yourself (requires `commot` already installed):

    import sys; sys.path.insert(0, "project/skills/ccc-commot/scripts")
    from ccc_commot import run_commot

There is ONE distance threshold, `dis_mult × median_nn` with `dis_mult` read from
the prep JSON log (1.5 — do not raise it). Do NOT add a second regime, add
cluster-level permutation tests, or change the score (summed OT flow). See
ccc-commot.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import json
import pandas as pd, scanpy as sc


def run_commot(adata, resource, dis_thr):
    """COMMOT spatial_communication on the shared resource -> LR-level scores.

    commot_score = total routed OT flow (sum of the per-pair spot x spot matrix). dis_thr is
    in native spatial units (a multiple of median_nn). Higher = more communication.
    """
    import commot as ct
    df = resource[["ligand", "receptor"]].copy()
    df["pathway"] = "unannotated"
    db = "shared"
    ct.tl.spatial_communication(
        adata, database_name=db, df_ligrec=df, dis_thr=dis_thr,
        heteromeric=False, pathway_sum=False, cost_type="euc",
    )
    rows = []
    for lig, rec in df[["ligand", "receptor"]].itertuples(index=False):
        key = f"commot-{db}-{lig}-{rec}"
        if key not in adata.obsp:                 # COMMOT did not route this pair (no signal)
            continue
        rows.append(dict(ligand=lig, receptor=rec, commot_score=float(adata.obsp[key].sum())))
    out = pd.DataFrame(rows)
    for store in (adata.obsp, adata.obsm, adata.uns):   # free the large per-pair matrices
        for k in [k for k in list(store.keys()) if k.startswith("commot-")]:
            del store[k]
    return out


def main():
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "commot"], check=True)

    prep = json.load(open("project/outputs/logs/ccc_data_prep.json"))
    median_nn, dis_mult = prep["median_nn"], prep.get("dis_mult", 1.5)
    if median_nn is None:
        raise ValueError("median_nn is null — COMMOT needs calibrated coords (see ccc-data-prep)")

    adata = sc.read_h5ad("project/outputs/ccc_base.h5ad")
    resource = pd.read_csv("project/outputs/ccc_lr_common.csv")[["ligand", "receptor"]]

    commot_df = run_commot(adata, resource, dis_thr=dis_mult * median_nn)
    commot_df.to_csv("project/outputs/commot_scores.csv", index=False)
    print(f"COMMOT done — {len(commot_df)} LR pairs routed at dis_thr={dis_mult * median_nn:.1f}")


if __name__ == "__main__":
    main()
