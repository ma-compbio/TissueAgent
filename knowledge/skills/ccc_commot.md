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
- `logs/ccc_data_prep.json` — READ `species`, `platform`, `resolution_mode`, `median_nn_um`, `n_cells_per_mm2`. Refuse if `median_nn_um` is null (see [[ccc-data-prep]] — pre-normalized coords make `dis_thr` meaningless).
- **`dis_thr` is split by signaling type** and derived from `median_nn_um` (all in µm):

  | Signaling category (CellChatDB) | `dis_thr` default | Rationale |
  |---|---|---|
  | `Cell-Cell Contact` | `max(3 × median_nn_um, 25)` | juxtacrine range — direct membrane contact |
  | `Secreted Signaling` | `max(10 × median_nn_um, 100)` | short-range paracrine diffusion |
  | `ECM-Receptor` | `max(15 × median_nn_um, 150)` | matrix-mediated, longer range |

  Platform sanity-check bands (µm) — cross-check the derived defaults land in these ranges before running:

  | Platform | contact | secreted | ECM |
  |---|---|---|---|
  | Visium (55 µm spots) | ~150 | ~500 | ~750 |
  | Visium HD (2 µm bins) | ~10 | ~50 | ~100 |
  | Xenium / MERFISH / seqFISH | ~15–30 | ~80–150 | ~150–250 |

  Using ONE `dis_thr` for all three signaling types is a scientific error at every resolution — a contact ligand evaluated at 500 µm produces spurious hits with everything in the same tissue domain.
- **Memory gate**: if `n_cells > 50_000` OR `n_cells_per_mm2 > 5_000`, subsample per FOV/section before proceeding. The spot×spot sparse OT matrices scale as O(n²) and OOM on imaging datasets otherwise.

## Output

Mutates the AnnData and re-writes `ccc_prepped.h5ad`. Key entries added:

| Location | Key | Content |
|---|---|---|
| `adata.obsp` | `commot-cellchat-<L>-<R>` | Sparse spot×spot matrix: row=sender spot, col=receiver spot, value=OT-routed signal |
| `adata.obsm` | `commot-cellchat-sum-sender` | DataFrame: per-spot total sent signal per pathway |
| `adata.obsm` | `commot-cellchat-sum-receiver` | DataFrame: per-spot total received signal per pathway |
| `adata.uns` | `commot_cluster-_ccc_cell_type-cellchat-<pathway>` | Dict with `communication_matrix` and `communication_pvalue` DataFrames |

Additional disk outputs:

- `commot_cluster_results.csv` — flat aggregation over all pathways, columns `[pathway, ligand, receptor, source, target, signaling_type, dis_thr_um, strength, pvalue]`. Each LR row carries the `dis_thr` (contact / secreted / ECM band) that produced it so aggregation can slot into the right regime.
- `logs/ccc_commot.json` — `{species, platform, resolution_mode, median_nn_um, n_lr_pairs_loaded, n_lr_pairs_after_filter, n_pathways, dis_thr_contact_um, dis_thr_secreted_um, dis_thr_ecm_um, n_cells_subsampled_from}`.

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
)  # -> DataFrame of surviving LR pairs. **Does NOT rename columns** (docstring
   # only promises "a DataFrame of filtered LR pairs"). Column names are still
   # the integer positions COMMOT ships. You MUST explicitly rename before passing
   # to spatial_communication:
   #     df_f.columns = ['ligand', 'receptor', 'pathway', 'signaling_type'][:df_f.shape[1]]

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
- ≥1 `commot-cellchat-*` key in `adata.obsp` per signaling regime (contact / secreted / ECM).
- `commot_cluster_results.csv` has ≥1 row with `pvalue ≤ 0.05`. If zero, verify the correct `dis_thr` band is being applied to the right signaling type — do not just relax the cutoff.
- `n_permutations == 500` recorded in `logs/ccc_commot.json`. Lower values (100) give a p-value floor of 0.01 and break RRA rank resolution downstream. Enforce 500 unless the memory gate forced a subsample.

## Workflow

1. `pip install commot` (persists in the `tissueagent-pyenv` volume; idempotent).
2. Load `ccc_prepped.h5ad` and `logs/ccc_data_prep.json`. Assert `obsm['spatial']` present and `median_nn_um is not None`.
3. **Memory gate.** If `n_cells > 50_000` or `n_cells_per_mm2 > 5_000`: subsample per FOV/section (record `n_cells_subsampled_from` in the log) before proceeding. Skip only with an explicit user override.
4. Derive per-regime `dis_thr` from `median_nn_um` per the table in **Input**. Cross-check the values land within the platform sanity-band; if not, ask the user before proceeding.
5. Load CellChatDB per signaling category, keeping the category tag:
   ```python
   dfs = []
   for cat in ["Cell-Cell Contact", "Secreted Signaling", "ECM-Receptor"]:
       d = ct.pp.ligand_receptor_database(species=species, signaling_type=cat, database="CellChat")
       d["signaling_type"] = cat
       dfs.append(d)
   ```
6. **Run three separate spatial_communication passes, one per regime**, each with its own `dis_thr` and `database_name` suffix (`cellchat_contact`, `cellchat_secreted`, `cellchat_ecm`) so the `obsp`/`uns` key namespaces stay disjoint:
   - For each regime: filter to that category's LRs, `ct.pp.filter_lr_database(...)` (RENAME columns manually — see cheatsheet), then `ct.tl.spatial_communication(adata, database_name=<regime>, df_ligrec=df_f_regime, dis_thr=<dis_thr_regime>, heteromeric=True, pathway_sum=True)`.
7. For each regime and each unique `pathway`:
   - `ct.tl.cluster_communication(adata, database_name=<regime>, pathway_name=p, clustering='_ccc_cell_type', n_permutations=500)`.
   - Pull `adata.uns[f'commot_cluster-_ccc_cell_type-{regime}-{p}']` and expand the cluster×cluster strength/p-value matrices into long-form rows, one per `(pathway, ligand, receptor, source, target)`, tagged with `signaling_type` and `dis_thr_um`.
8. Write `commot_cluster_results.csv` and the JSON log, re-write `ccc_prepped.h5ad`.

## Code Template

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "commot"], check=True)

import json, os
import pandas as pd
import scanpy as sc
import commot as ct

with open("logs/ccc_data_prep.json") as f:
    prep = json.load(f)

species         = prep["species"]
platform        = prep["platform"]
median_nn_um    = prep["median_nn_um"]
n_cells_per_mm2 = prep.get("n_cells_per_mm2")
if median_nn_um is None:
    raise ValueError("median_nn_um is null — commot requires physical coords")

adata = sc.read_h5ad("ccc_prepped.h5ad")
n_cells_subsampled_from = None

# Memory gate
if adata.n_obs > 50_000 or (n_cells_per_mm2 and n_cells_per_mm2 > 5_000):
    n_cells_subsampled_from = int(adata.n_obs)
    # simple stratified subsample by cell type; replace with per-FOV split if fov col exists
    idx = (adata.obs.groupby("_ccc_cell_type", observed=True)
                    .apply(lambda x: x.sample(min(len(x), 2000), random_state=1337))
                    .reset_index(level=0, drop=True).index)
    adata = adata[idx].copy()

# Per-regime dis_thr from median_nn_um
dis_thr = {
    "contact":  max(3.0  * median_nn_um,  25.0),
    "secreted": max(10.0 * median_nn_um, 100.0),
    "ecm":      max(15.0 * median_nn_um, 150.0),
}
CAT_TO_REGIME = {
    "Cell-Cell Contact":  "contact",
    "Secreted Signaling": "secreted",
    "ECM-Receptor":       "ecm",
}

rows, pathways_by_regime = [], {}
for cat, regime in CAT_TO_REGIME.items():
    db = f"cellchat_{regime}"

    df = ct.pp.ligand_receptor_database(species=species, signaling_type=cat, database="CellChat")
    df_f = ct.pp.filter_lr_database(df, adata, min_cell_pct=0.05)
    # COMMOT does NOT rename columns — do it explicitly:
    df_f.columns = ["ligand", "receptor", "pathway", "signaling_type"][:df_f.shape[1]]
    if df_f.empty:
        continue

    ct.tl.spatial_communication(
        adata,
        database_name=db,
        df_ligrec=df_f,
        dis_thr=dis_thr[regime],
        heteromeric=True,
        pathway_sum=True,
    )

    pathways = df_f["pathway"].dropna().unique().tolist()
    pathways_by_regime[regime] = len(pathways)

    for p in pathways:
        ct.tl.cluster_communication(
            adata, database_name=db, pathway_name=p,
            clustering="_ccc_cell_type", n_permutations=500,
        )
        key = f"commot_cluster-_ccc_cell_type-{db}-{p}"
        if key not in adata.uns:
            continue
        cdf = adata.uns[key]
        strength = cdf["communication_matrix"]
        pvals    = cdf["communication_pvalue"]
        lrs = df_f.loc[df_f["pathway"] == p, ["ligand", "receptor"]]
        for src in strength.index:
            for tgt in strength.columns:
                s, pv = float(strength.loc[src, tgt]), float(pvals.loc[src, tgt])
                for _, lr in lrs.iterrows():
                    rows.append({
                        "pathway": p, "ligand": lr["ligand"], "receptor": lr["receptor"],
                        "source": src, "target": tgt,
                        "signaling_type": cat, "dis_thr_um": dis_thr[regime],
                        "strength": s, "pvalue": pv,
                    })

os.makedirs("logs", exist_ok=True)
pd.DataFrame(rows).to_csv("commot_cluster_results.csv", index=False)
json.dump({
    "species": species, "platform": platform,
    "resolution_mode": prep["resolution_mode"],
    "median_nn_um": median_nn_um,
    "dis_thr_contact_um":  dis_thr["contact"],
    "dis_thr_secreted_um": dis_thr["secreted"],
    "dis_thr_ecm_um":      dis_thr["ecm"],
    "n_pathways_by_regime": pathways_by_regime,
    "n_permutations": 500,
    "n_cells_subsampled_from": n_cells_subsampled_from,
}, open("logs/ccc_commot.json", "w"), indent=2)
adata.write("ccc_prepped.h5ad")
print("COMMOT done; regimes:", pathways_by_regime)
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
