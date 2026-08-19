"""CCC ensemble — Step 6 (final): mean-of-percentile-ranks consensus.

Directly runnable AND importable. Run the whole step in the kernel with:

    %run project/skills/ccc-aggregate/scripts/ccc_aggregate.py

or import the combiner and call it yourself:

    import sys; sys.path.insert(0, "project/skills/ccc-aggregate/scripts")
    from ccc_aggregate import build_ensemble

The ensemble score is the MEAN of the four members' percentile ranks (ranked AFTER
the inner join). Do NOT change the combiner (not `min`, not weighted), drop or add
a member, or add p-values/FDR. See ccc-aggregate.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import pandas as pd

MEMBER_SCORE = {
    "liana": "liana_score", "commot": "commot_score",
    "stlearn": "stlearn_score", "decoupler": "decoupler_score",
}


def build_ensemble(member_dfs, resource):
    """Mean-of-percentile-ranks consensus over the shared universe.

    member_dfs: dict {name: DataFrame[ligand, receptor, <name>_score]}. Universe = pairs
    scored by ALL members (inner join). Percentile-rank each member score AFTER the join,
    then ensemble_score = mean of the four ranks. Sorted descending.
    """
    uni = resource[["ligand", "receptor"]].drop_duplicates()
    for name, df in member_dfs.items():
        col = MEMBER_SCORE[name]
        uni = uni.merge(df[["ligand", "receptor", col]], on=["ligand", "receptor"], how="inner")
    uni = uni.reset_index(drop=True)
    pct_cols = []
    for name in member_dfs:
        uni[f"{name}_pct"] = uni[MEMBER_SCORE[name]].rank(pct=True)
        pct_cols.append(f"{name}_pct")
    uni["ensemble_score"] = uni[pct_cols].mean(axis=1)
    return uni.sort_values("ensemble_score", ascending=False).reset_index(drop=True)


def main():
    resource = pd.read_csv("project/outputs/ccc_lr_common.csv")[["ligand", "receptor"]]
    member_dfs = {
        "liana":     pd.read_csv("project/outputs/liana_scores.csv"),
        "commot":    pd.read_csv("project/outputs/commot_scores.csv"),
        "stlearn":   pd.read_csv("project/outputs/stlearn_scores.csv"),
        "decoupler": pd.read_csv("project/outputs/decoupler_scores.csv"),
    }

    uni = build_ensemble(member_dfs, resource)
    uni.to_csv("project/outputs/ccc_ensemble.csv", index=False)
    print(f"Ensemble — {len(uni)} LR pairs scored by ALL four members")
    print(uni.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
