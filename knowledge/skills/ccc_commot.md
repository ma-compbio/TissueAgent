---
name: ccc-commot
description: Run COMMOT (collective optimal transport) on the shared CCC resource — spatial_communication at two distance thresholds (contact + diffusion, in native coordinate units), then per-LR cluster_communication with permutation p-values and BH correction. Emits one standardized long CSV for the ensemble aggregator plus its operable LR universe.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport]
status: enable
---

# CCC — COMMOT

## When to use

Step 3 of the `ccc_ensemble` plan. COMMOT scores communication with a **spatial
optimal-transport** problem on the cell/spot graph: an interaction is strong between two
locations if the ligand is locally available, the receptor is within `dis_thr`, and the OT
solution routes flow between them. This is spatially sensitive in a way LIANA's
`rank_aggregate` is not. Requires `obsm['spatial']`; don't run on non-spatial data.

Like every method in the ensemble it runs on the **shared resource** from [[ccc-data-prep]]
(`ccc_lr_common.csv`), passed as `df_ligrec` — never its native CellChatDB — so the three
methods test the same pairs and disagreement isn't a database artifact.

Install: `pip install commot` (idempotent; the coding image also pre-installs it).

## Input

- `ccc_base.h5ad` (copy it) — `.X` log1p-normalized, `obsm['spatial']`, `_ccc_cell_type`.
- `ccc_lr_common.csv` — shared monomeric resource.
- `logs/ccc_data_prep.json` — read `species`, `resolution_mode`, `median_nn` (native units),
  `sample_col`, `n_cells`.

## Distance thresholds (native units, two regimes)

`dis_thr` is in the units of `obsm['spatial']` — COMMOT does **not** convert pixels to µm. So
derive it from `median_nn` (already in those units):

| Regime | `dis_thr` | Meaning |
|---|---|---|
| contact | `1.5 × median_nn` | immediate-neighbour / juxtacrine-ish (at Visium ~100 µm pitch ≈ 150 µm; true cell contact is unresolved on spots — call it "short-range spot association") |
| diffusion | `3 × median_nn` | short-range paracrine |

Run **both** and keep them as separate regimes (a conclusion that flips between them is
scale-sensitive — report that, don't pick the flattering radius). Using one `dis_thr` for all
biology is the error the old skill made.

## Memory guard (do NOT randomly subsample)

COMMOT stores an `n×n` sparse matrix per LR pair; cost grows fast. If `n_cells` is large
(≳50k) or very dense: run **per section/FOV** (`sample_col`) or per anatomical ROI. Global
random subsampling **changes the OT solution** (it alters local ligand/receptor supply) and
is not equivalent to the full tissue — if you must reduce size, tile with a halo ≥ `dis_thr`
and keep only tile-interior edges. Record what was and wasn't evaluated; never crop-until-it-runs.

## Output

- `commot_ccc.csv` — standardized long table for [[ccc-aggregate]]: per-LR, per-(source,
  target), per-regime cluster results. Schema `engine, mode, regime, level, spatial, ligand,
  receptor, source, target, score, higher_better, pvalue, contrib_dist`. `score` = OT
  cluster strength (higher=stronger); `pvalue` = per-LR permutation p (BH-corrected column
  `qvalue` also kept in a side file); `contrib_dist` = median distance (native units) of the
  sender→receiver pairs carrying nonzero signal (feeds the aggregator's autocrine filter).
- `commot_universe.csv` — operable pairs: shared pairs whose both genes are on the panel
  and survive `filter_lr_database`.
- `logs/ccc_commot.json` — `{species, dis_thr_contact, dis_thr_diffusion, n_pairs_routed,
  n_permutations, n_sig_bh, subsampled}`.

## API cheatsheet (COMMOT 0.0.3 — use verbatim)

```python
ct.tl.spatial_communication(
    adata, database_name="shared_contact", df_ligrec=<lig,rec,pathway>,
    dis_thr=<scalar>,          # REQUIRED positive scalar; dis_thr=None -> AttributeError
    heteromeric=False,         # monomeric shared resource
    pathway_sum=False,         # don't fuse all pairs into one fake pathway
    cost_type="euc",
)  # writes obsp['commot-<db>-<L>-<R>'], obsm['commot-<db>-sum-{sender,receiver}'],
   #        uns['commot-<db>-info']

ct.tl.cluster_communication(
    adata, database_name="shared_contact", lr_pair=(L, R),   # per-LR, NOT pathway_name=
    clustering="_ccc_cell_type", n_permutations=500, random_seed=1,
)  # writes uns['commot_cluster-_ccc_cell_type-<db>-<L>-<R>'] =
   #   {'communication_matrix': df[src×tgt], 'communication_pvalue': df[src×tgt]}
```

Call per **LR pair** (`lr_pair=`), not per pathway: a pathway-level call gives one p-value to
every LR in the pathway, tying their ranks so the consensus can't separate them. Iterate the
`commot-<db>-<L>-<R>` obsp keys COMMOT actually wrote (the routed set), and iterate the
resource **rows** to recover `(L,R)` — gene symbols can contain `-` (HLA-A), so splitting the
obsp key string on `-` is unsafe.

## Success criteria

- ≥1 `commot-*` obsp key per regime; `commot_ccc.csv` non-empty.
- `n_permutations == 500` in the log (100 gives a 0.01 p-floor that flattens ranks).
- If zero significant pairs: check gene symbols, `dis_thr` units, and species — do **not**
  just relax the p-cutoff.

## Code template

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "commot"], check=True)
import json
import numpy as np, pandas as pd, scanpy as sc, scipy.sparse as sp, commot as ct
from statsmodels.stats.multitest import multipletests

prep = json.load(open("logs/ccc_data_prep.json"))
species, res_mode, median_nn = prep["species"], prep["resolution_mode"], prep["median_nn"]
if median_nn is None:
    raise ValueError("median_nn is null — COMMOT needs calibrated coords (see ccc-data-prep)")

adata = sc.read_h5ad("ccc_base.h5ad")             # copy of the immutable base
resource = pd.read_csv("ccc_lr_common.csv")[["ligand", "receptor"]].copy()
resource["pathway"] = "unannotated"

# Memory guard: run per-section if huge; NEVER global random subsample.
subsampled = False
if adata.n_obs > 50_000 and prep.get("sample_col"):
    subsampled = "per_sample_recommended"   # loop sample_col upstream; template shows 1 section

coords = np.asarray(adata.obsm["spatial"], float)
labels = adata.obs["_ccc_cell_type"].astype(str).to_numpy()

def contrib_dist(M):
    """Median native-unit distance of nonzero sender->receiver pairs, per (src,tgt)."""
    M = sp.coo_matrix(M)
    out = {}
    for src in np.unique(labels):
        for tgt in np.unique(labels):
            keep = (labels[M.row] == src) & (labels[M.col] == tgt) & (M.data != 0)
            out[(src, tgt)] = (float(np.median(np.linalg.norm(
                coords[M.row[keep]] - coords[M.col[keep]], axis=1))) if keep.any() else np.nan)
    return out

regimes = {"contact": 1.5 * median_nn, "diffusion": 3.0 * median_nn}
rows, n_routed = [], 0
for regime, dis_thr in regimes.items():
    db = f"shared_{regime}"
    ct.tl.spatial_communication(adata, database_name=db, df_ligrec=resource,
                                dis_thr=dis_thr, heteromeric=False,
                                pathway_sum=False, cost_type="euc")
    for lig, rec in resource[["ligand", "receptor"]].itertuples(index=False):
        key = f"commot-{db}-{lig}-{rec}"
        if key not in adata.obsp:            # COMMOT didn't route this pair here
            continue
        n_routed += 1
        ct.tl.cluster_communication(adata, database_name=db, lr_pair=(lig, rec),
                                    clustering="_ccc_cell_type",
                                    n_permutations=500, random_seed=1)
        ck = f"commot_cluster-_ccc_cell_type-{db}-{lig}-{rec}"
        if ck not in adata.uns:
            continue
        strength = adata.uns[ck]["communication_matrix"]     # rows=source, cols=target
        pvals = adata.uns[ck]["communication_pvalue"]
        cdist = contrib_dist(adata.obsp[key])
        for src in strength.index:
            for tgt in strength.columns:
                rows.append(dict(engine="commot", mode="cluster", regime=regime,
                                 level="celltype_pair", spatial=True,
                                 ligand=lig, receptor=rec, source=src, target=tgt,
                                 score=float(strength.loc[src, tgt]), higher_better=True,
                                 pvalue=float(pvals.loc[src, tgt]),
                                 contrib_dist=cdist.get((src, tgt), np.nan)))

out = pd.DataFrame(rows)
if len(out):
    out["qvalue"] = multipletests(out["pvalue"].fillna(1.0), method="fdr_bh")[1]
    out.drop(columns="qvalue").to_csv("commot_ccc.csv", index=False)
    out.to_csv("commot_ccc_with_bh.csv", index=False)      # BH side file for reporting
else:
    out.to_csv("commot_ccc.csv", index=False)

# operable universe = shared pairs surviving COMMOT's expression filter
filt = ct.pp.filter_lr_database(resource.copy(), adata, min_cell_pct=0.05)
filt.columns = ["ligand", "receptor", "pathway"][:filt.shape[1]]
filt[["ligand", "receptor"]].to_csv("commot_universe.csv", index=False)

json.dump({"species": species, "dis_thr_contact": regimes["contact"],
           "dis_thr_diffusion": regimes["diffusion"], "n_pairs_routed": n_routed,
           "n_permutations": 500,
           "n_sig_bh": int((out["qvalue"] < 0.05).sum()) if len(out) and "qvalue" in out else 0,
           "subsampled": subsampled}, open("logs/ccc_commot.json", "w"), indent=2)
print(f"COMMOT done — routed {n_routed} LR pairs across regimes")
```

## Common issues

- **`dis_thr=None` → `AttributeError` (no `cutoff`).** Always pass a positive scalar.
- **Wrong units → all-zero or saturated.** `dis_thr` is in coordinate units; this skill
  derives it from `median_nn`, so it's correct whether coords are pixels or µm.
- **Ensembl IDs → 0 pairs silently.** `filter_lr_database` returns ~nothing against Ensembl;
  [[ccc-data-prep]] guarantees symbols.
- **Per-LR vs per-pathway.** Use `lr_pair=`; a `pathway_name=` call ties every LR in the
  pathway to one p-value.
- **`commot.__version__` doesn't exist** — use `importlib.metadata.version('commot')`.
- **uns dict keys vary across releases.** After the first `cluster_communication`,
  `print(list(adata.uns[ck].keys()))` and adapt if `communication_matrix`/`communication_pvalue`
  are renamed.

## References

- COMMOT: Cang et al., *Nature Methods* 2023. Docs: <https://commot.readthedocs.io/>
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-stlearn]], [[ccc-aggregate]].
