---
name: ccc-commot
description: Run COMMOT (Collective Optimal transport for Multi-Omics inference of cell-cell communicaTion) on preprocessed spatial AnnData — installs commot if needed, loads species-matched CellChatDB ligand-receptor pairs, runs spatial_communication, then cluster_communication per pathway with permutation p-values. Designed to slot into the ccc_ensemble plan.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport]
status: enable
---

# CCC — COMMOT spatial communication

## When to use

Step 3 of the `ccc_ensemble` plan. COMMOT differs from LIANA+ in that it scores communication using a **spatial optimal-transport** problem on the spot graph — an interaction is "strong" between two spots if the ligand is locally available, the receptor is nearby within `dis_thr`, and the OT solution routes flow between them. This is sensitive to spatial layout in a way that LIANA+ is not.

Don't use it on non-spatial single-cell data (it requires `obsm['spatial']`).

## Input

- `ccc_prepped.h5ad` from [[ccc-data-prep]] — `.X` = log1p-normalized (unscaled, min≥0), `obsm['spatial']` set, `obs['_ccc_cell_type']` populated, `layers['counts']` preserved, `var_names` = gene symbols matching CellChatDB (not Ensembl IDs — COMMOT will silently return empty signal otherwise).
- `dis_thr` (distance threshold for spatial communication, **in units of `obsm['spatial']`** — typically pixels for Visium HiRes or microns for Xenium). Default 500 for Visium; for Xenium use ~150–200 µm. Confirm units with the user before running. If the user can't say, sample 2000 spots, compute pairwise Euclidean distance, and start at the 95th percentile.
- Species — `"human"` or `"mouse"`. Other species require ortholog mapping upstream.

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

## API cheatsheet

Signatures of the five functions used below — verified against COMMOT 0.0.3 docs. See `search_documentation(library='commot', name=...)` for full parameter descriptions. You should generally use the parameter values (e.g. cot_intermax, n_permutations) given below or the default ones supplied by COMMOT, unless you have a reason to deviate from them. Justify these reasons, if any, in your response.

```python
ct.pp.ligand_receptor_database(
    database='CellChat',      # or 'CellPhoneDB_v4.0'
    species='mouse',          # or 'human' — only these two are first-class
    heteromeric_delimiter='_',
    signaling_type='Secreted Signaling',  # or 'Cell-Cell Contact', 'ECM-Receptor', or None for all
)  # -> DataFrame with INTEGER column names [0,1,2,3] = ligand, receptor, pathway, category

ct.pp.filter_lr_database(
    df_ligrec, adata,
    heteromeric=True, heteromeric_delimiter='_', heteromeric_rule='min',
    filter_criteria='min_cell_pct', min_cell=100, min_cell_pct=0.05,
)  # -> DataFrame RENAMED to columns ['ligand', 'receptor', 'pathway']

ct.tl.spatial_communication(
  cost_type='euc', cot_eps_p=0.1, cot_rho=10.0, cot_nitermax=10000,
    cot_weights=(0.25,0.25,0.25,0.25), copy=False,
)  # -> writes adata.obsp['commot-<db>-<L>-<R>'], adata.obsm['commot-<db>-sum-{sender,receiver}']

ct.tl.cluster_communication(
    adata, database_name, pathway_name=None, lr_pair=None,   # exactly one of these two
    clustering='_ccc_cell_type', n_permutations=500, random_seed=1,
)  # LABEL permutation — fast, USE THIS. Writes adata.uns['commot_cluster-<clustering>-<db>-<key>']

ct.tl.cluster_communication_spatial_permutation(
    adata, df_ligrec, database_name, dis_thr, clustering,
    heteromeric=True, heteromeric_rule='min',
    perm_type='within_cluster', n_permutations=100, cot_nitermax=100,
)  # LOCATION permutation — recomputes OT per permutation, ~100x slower.
   # Only use when the user explicitly asks for a spatially-conservative null.
   # Writes adata.uns['commot_cluster_spatial_permutation-<db>-<clustering>-<L>-<R>'] (different prefix!)
```

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
   - `ct.tl.cluster_communication(adata, database_name='cellchat', pathway_name=p, clustering='_ccc_cell_type', n_permutations=100)`.
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

- **`dis_thr=None` crashes.** `spatial_communication` and `cluster_communication_spatial_permutation` accept `dis_thr=None` per the signature, but internally `CellCommunication.__init__` only assigns `self.cutoff` on the scalar/dict branch. Passing `None` produces `AttributeError: 'CellCommunication' object has no attribute 'cutoff'` at the first OT call. **Always pass a positive scalar.** If the user hasn't given one, sample ~2000 spots and use the 95th-percentile pairwise Euclidean distance as a starting point.
- **`dis_thr` in wrong units → all signal is zero (too small) or saturated (too large).** Confirm coord units (pixels vs µm) before running; default 500 is Visium-pixel-scale.
- **`var_names` must be gene symbols, not Ensembl IDs.** The `ccc-data-prep` skill guarantees this, but if you ever handle a raw AnnData, `filter_lr_database` will return ~0 pairs against Ensembl IDs with no error.
- **Small targeted panels leave few LR pairs after filtering.** Xenium/MERSCOPE panels of a few hundred genes typically drop from ~1200 CellChatDB pairs to 10–30 after `filter_lr_database`. That's expected — don't loosen `min_cell_pct` to hunt for more pairs unless the biology actually warrants it.
- **`cluster_communication` vs `cluster_communication_spatial_permutation`.** The permutation-suffixed variant recomputes the OT for every permutation and is roughly two orders of magnitude slower. Use plain `cluster_communication` (label permutation) by default. Only reach for the spatial-permutation variant when the user explicitly needs a spatial null (they want to rule out that observed strengths could arise from cluster-adjacency alone).
- **`commot.__version__` doesn't exist.** If you need a version, use `importlib.metadata.version('commot')` — the module has no `__version__` attribute.
- **Pathway naming with `/` or spaces.** COMMOT keys pathways verbatim; if the name contains punctuation, the join in plan step 5 must use the exact string. Don't normalize the name.
- **`pathway_sum=True` is required** for the `commot-cellchat-sum-receiver` / `-sum-sender` aggregates the ensemble plots use.
- **Memory.** For >50k spots the spot×spot sparse matrices blow up. Subsample first or run per-section.
- **CellChatDB species coverage.** Only human and mouse are first-class. For other species use ortholog-mapping before this skill.
- **Schema drift between COMMOT versions.** The `adata.uns[...]` dict keys (`communication_matrix`, `communication_pvalue`) have varied across releases. After the first `cluster_communication` call, `print(list(adata.uns[key].keys()))` and adapt the loop if names differ.
- **Two uns key prefixes.** `cluster_communication` writes under `commot_cluster-<clustering>-<db>-<key>`. `cluster_communication_spatial_permutation` writes under `commot_cluster_spatial_permutation-<db>-<clustering>-<L>-<R>`. Flat-aggregation code that iterates `adata.uns` must handle both prefixes if you use the spatial variant.

## References

- COMMOT paper: Cang et al., *Nature Methods* 2023 — "Screening cell-cell communication in spatial transcriptomics via collective optimal transport."
- COMMOT docs: <https://commot.readthedocs.io/>
- Visium tutorial: <https://commot.readthedocs.io/en/latest/notebooks/visium-mouse_brain.html>
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-stlearn]].
