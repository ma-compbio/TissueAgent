---
name: ccc-commot
description: Run COMMOT (Collective Optimal transport for Multi-Omics inference of cell-cell communicaTion) on preprocessed spatial AnnData — installs commot if needed, loads species-matched CellChatDB ligand-receptor pairs, runs spatial_communication, then cluster_communication per pathway with permutation p-values. Designed to slot into the ccc_ensemble plan.
applies_to: [coding]
tags: [ccc, commot, spatial, optimal-transport]
status: enable
---

# CCC — COMMOT spatial communication

## When to use

Step 3 of the `ccc_ensemble` plan. COMMOT differs from LIANA+ in that it scores communication using a **spatial optimal-transport** problem on the spot graph — an interaction is "strong" between two spots if the ligand is locally available, the receptor is nearby within `dis_thr`, and the OT solution routes flow between them. This is sensitive to spatial layout in a way that LIANA+ is not.

Don't use it on non-spatial single-cell data (it requires `obsm['spatial']`).

## Input

- `ccc_prepped.h5ad` from [[ccc-data-prep]] — `.X` = log1p-normalized, `obsm['spatial']` set, `obs['_ccc_cell_type']` populated, `layers['counts']` preserved.
- `dis_thr` (distance threshold for spatial communication, **in units of `obsm['spatial']`** — typically pixels for Visium HiRes or microns for Xenium). Default 500 for Visium; for Xenium use ~150–200 µm. Confirm units with the user before running.
- Species — `"human"` or `"mouse"`.

## Output

Mutates the AnnData and re-writes `ccc_prepped.h5ad`. Key entries added:

| Location | Key | Content |
|---|---|---|
| `adata.obsp` | `commot-cellchat-<L>-<R>` | Sparse spot×spot matrix: row=sender spot, col=receiver spot, value=OT-routed signal |
| `adata.obsm` | `commot-cellchat-sum-sender` | DataFrame: per-spot total sent signal per pathway |
| `adata.obsm` | `commot-cellchat-sum-receiver` | DataFrame: per-spot total received signal per pathway |
| `adata.uns` | `commot_cluster-_ccc_cell_type-cellchat-<pathway>` | Dict with `communication_matrix` and `communication_pvalue` DataFrames |

Additional disk outputs:

- `commot_cluster_results.csv` — flat aggregation over all pathways, columns `[pathway, ligand, receptor, source, target, strength, pvalue]`, where each pathway row is expanded to its constituent LR pairs (from the loaded `df_ligrec`) — the aggregation step (plan step 5) consumes this CSV.
- `logs/ccc_commot.json` — `{n_lr_pairs_loaded, n_lr_pairs_after_filter, n_pathways, dis_thr, species}`.

## Success Criteria

- `commot` import succeeds after install.
- ≥1 `commot-cellchat-*` key in `adata.obsp`.
- `commot_cluster_results.csv` has ≥1 row with `pvalue ≤ 0.05`. If zero, lower `dis_thr` or check that cell types are spatially adjacent at all — do not just relax the cutoff.

## Workflow

1. `pip install commot` (persists in the `tissueagent-pyenv` volume; idempotent).
2. Load `ccc_prepped.h5ad`. Assert `obsm['spatial']` present.
3. Load CellChatDB across all three signaling categories: `ct.pp.ligand_receptor_database(species=species, signaling_type=<cat>, database='CellChat')` for `'Secreted Signaling'`, `'Cell-Cell Contact'`, `'ECM-Receptor'`. Concat + dedupe — this gives ensemble parity with LIANA's `consensus` resource breadth.
4. Filter to LRs expressed in the data: `df_f = ct.pp.filter_lr_database(df, adata, min_cell_pct=0.05)`.
5. `ct.tl.spatial_communication(adata, database_name='cellchat', df_ligrec=df_f, dis_thr=<dis_thr>, heteromeric=True, pathway_sum=True)`.
6. For each unique `pathway` in `df_f['pathway']`:
   - `ct.tl.cluster_communication(adata, database_name='cellchat', pathway_name=p, clustering='_ccc_cell_type', n_permutations=500)`.
   - Pull `adata.uns[f'commot_cluster-_ccc_cell_type-cellchat-{p}']` and expand the cluster×cluster strength/p-value matrices into long-form rows, one per `(pathway, ligand, receptor, source, target)`.
7. Write `commot_cluster_results.csv` and the JSON log, re-write `ccc_prepped.h5ad`.

## Code Template

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "commot"], check=True)

import json, os
import pandas as pd
import scanpy as sc
import commot as ct

adata = sc.read_h5ad("ccc_prepped.h5ad")
species = "human"   # read from logs/ccc_data_prep.json
dis_thr = 500       # adjust to coord units

# 1. Build species-matched LR DB across all three CellChat categories
dfs = []
for cat in ["Secreted Signaling", "Cell-Cell Contact", "ECM-Receptor"]:
    dfs.append(ct.pp.ligand_receptor_database(species=species, signaling_type=cat, database="CellChat"))
df = pd.concat(dfs, ignore_index=True).drop_duplicates()
df_f = ct.pp.filter_lr_database(df, adata, min_cell_pct=0.05)

# 2. Spatial communication
ct.tl.spatial_communication(
    adata,
    database_name="cellchat",
    df_ligrec=df_f,
    dis_thr=dis_thr,
    heteromeric=True,
    pathway_sum=True,
)

# 3. Per-pathway cluster permutation test
rows = []
pathways = df_f["pathway"].dropna().unique().tolist()
for p in pathways:
    ct.tl.cluster_communication(
        adata, database_name="cellchat", pathway_name=p,
        clustering="_ccc_cell_type", n_permutations=500,
    )
    key = f"commot_cluster-_ccc_cell_type-cellchat-{p}"
    if key not in adata.uns:
        continue
    cdf = adata.uns[key]
    strength = cdf["communication_matrix"]
    pvals    = cdf["communication_pvalue"]
    lrs_in_pathway = df_f.loc[df_f["pathway"] == p, ["ligand", "receptor"]]
    for src in strength.index:
        for tgt in strength.columns:
            s = float(strength.loc[src, tgt])
            pv = float(pvals.loc[src, tgt])
            for _, lr in lrs_in_pathway.iterrows():
                rows.append({"pathway": p, "ligand": lr["ligand"], "receptor": lr["receptor"],
                             "source": src, "target": tgt,
                             "strength": s, "pvalue": pv})

os.makedirs("logs", exist_ok=True)
pd.DataFrame(rows).to_csv("commot_cluster_results.csv", index=False)
json.dump({"species": species, "dis_thr": dis_thr,
           "n_lr_pairs_loaded": int(len(df)),
           "n_lr_pairs_after_filter": int(len(df_f)),
           "n_pathways": len(pathways)},
          open("logs/ccc_commot.json", "w"), indent=2)
adata.write("ccc_prepped.h5ad")
print("COMMOT done; pathways:", len(pathways))
```

## Common Issues

- **`dis_thr` in wrong units → all signal is zero (too small) or saturated (too large).** Confirm coord units (pixels vs µm) before running; default 500 is Visium-pixel-scale.
- **Pathway naming with `/` or spaces.** COMMOT keys pathways verbatim; if the name contains punctuation, the join in plan step 5 must use the exact string. Don't normalize the name.
- **`pathway_sum=True` is required** for the `commot-cellchat-sum-receiver` / `-sum-sender` aggregates the ensemble plots use.
- **Memory.** For >50k spots the spot×spot sparse matrices blow up. Subsample first or run per-section.
- **CellChatDB species coverage.** Only human and mouse are first-class. For other species use ortholog-mapping before this skill.
- **Schema drift between COMMOT versions.** The `adata.uns[...]` dict keys (`communication_matrix`, `communication_pvalue`) have varied across releases. After the first `cluster_communication` call, `print(list(adata.uns[key].keys()))` and adapt the loop if names differ.

## References

- COMMOT paper: Cang et al., *Nature Methods* 2023 — "Screening cell-cell communication in spatial transcriptomics via collective optimal transport."
- COMMOT docs: <https://commot.readthedocs.io/>
- Visium tutorial: <https://commot.readthedocs.io/en/latest/notebooks/visium-mouse_brain.html>
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-stlearn]].
