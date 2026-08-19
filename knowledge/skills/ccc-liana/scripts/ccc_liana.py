"""CCC ensemble — Step 2: LIANA+ rank_aggregate (expression-consensus axis).

Directly runnable AND importable. Run the whole step in the kernel with:

    %run project/skills/ccc-liana/scripts/ccc_liana.py

or import the scorer and call it yourself:

    import sys; sys.path.insert(0, "project/skills/ccc-liana/scripts")
    from ccc_liana import run_liana

Do NOT edit the function body, reimplement the scoring, swap the scoring axis,
add `bivariate`, change `use_raw`, or groupby anything other than `_ct`. This is
the validated implementation — see ccc-liana.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import json
import pandas as pd, scanpy as sc


def run_liana(adata, resource, expr_prop=0.1, seed=1337, n_perms=100):
    """LIANA+ rank_aggregate on the shared resource -> LR-level scores.

    liana_score = 1 - min magnitude_rank over all (source,target) cell-group pairs.
    use_raw=False is critical (LIANA defaults True and would silently use a stale .raw).
    n_perms is low on purpose: magnitude_rank is deterministic (expression means), so
    permutations barely move the ranking axis but are the slow step.
    """
    import liana as li
    li.mt.rank_aggregate(
        adata, groupby="_ct", resource=resource[["ligand", "receptor"]],
        use_raw=False, expr_prop=expr_prop, min_cells=10, n_perms=n_perms,
        seed=seed, verbose=False,
    )
    lr = adata.uns["liana_res"]
    g = (lr.assign(mag=lr["magnitude_rank"])
           .groupby(["ligand_complex", "receptor_complex"])["mag"].min().reset_index())
    g.columns = ["ligand", "receptor", "min_mag_rank"]
    g["liana_score"] = 1.0 - g["min_mag_rank"]
    return g[["ligand", "receptor", "liana_score"]], lr


def main():
    prep = json.load(open("project/outputs/logs/ccc_data_prep.json"))
    adata = sc.read_h5ad("project/outputs/ccc_base.h5ad")
    resource = pd.read_csv("project/outputs/ccc_lr_common.csv")[["ligand", "receptor"]]

    liana_df, lr = run_liana(adata, resource, expr_prop=0.05 if prep.get("small_panel") else 0.1)
    liana_df.to_csv("project/outputs/liana_scores.csv", index=False)
    print(f"LIANA done — {len(liana_df)} LR pairs scored")


if __name__ == "__main__":
    main()
