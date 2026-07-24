#!/usr/bin/env python3
"""Cross-method CCC consensus for the ``ccc_ensemble`` workflow.

Combines LIANA+, COMMOT, and stLearn ligand-receptor calls into a
**within-method percentile-rank consensus**. Importable
(``from ccc_aggregate import ...``) or runnable as a CLI (``--help``).

WHY THIS IS SIMPLE NOW
----------------------
The hard problem in cross-method CCC is that the three tools' native databases
disagree on membership *and* granularity (LIANA/COMMOT name the complex
``TGFBR1_TGFBR2``; stLearn names the single gene ``TGFBR1``; CellChatDB and
connectomeDB overlap only ~0.17 Jaccard). We solve that **upstream** in
``ccc-data-prep``: all three methods run on ONE shared LIANA-consensus resource
(monomeric common core for the 3-method lane), so every method reports the same
single-gene ``(ligand, receptor)`` universe. Aggregation is therefore a clean
join — no complex explosion, no per-DB reconciliation.

The audit's guidance is deliberately followed: convert each method's native
score to a **within-method percentile rank** over the shared universe, then take
the consensus of those ranks. The result is a descriptive *consensus rank*, not
an RRA p-value (custom RRA is not calibrated across these heterogeneous lists).

INPUT — one standardized long CSV per method (see ``references/method-io.md``):
    engine, mode, regime, level, spatial, ligand, receptor, source, target,
    score, higher_better, pvalue, contrib_dist

CONSENSUS SEMANTICS (read before editing)
-----------------------------------------
- Votes count per **engine** (``liana``/``commot``/``stlearn``), never per mode.
  LIANA ``rank_aggregate`` (co-expression) and ``bivariate`` (spatial) are two
  modes of ONE engine.
- The directed cell-type consensus is over ``(ligand, receptor, source, target)``
  triples at ``level == "celltype_pair"``: LIANA ``rank_aggregate`` (regime
  ``coexpr``, non-spatial), COMMOT ``cluster`` (spatial), stLearn ``cci``
  (spatial, undirected support). LIANA ``bivariate`` is LR-level and corroborates
  a triple's LR pair (``lr_spatial_support``) but never invents a direction.
- ``require_spatial`` drops a spatially-labelled row supported only by LIANA
  ``rank_aggregate`` (co-expression is not spatial communication).
- On ``single_cell`` platforms the autocrine-spillover filter drops
  ``source==target`` triples whose contributing distance is below
  ``factor * median_nn`` (segmentation bleed), using ``contrib_dist``.
- Missing = NaN, never 0. ``n_capable`` (engines whose shared universe contained
  the pair) is reported next to ``n_sig`` (engines that agreed).
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

COEXPR = "coexpr"        # LIANA rank_aggregate: non-spatial cluster co-expression
CONTACT = "contact"      # juxtacrine scale
DIFFUSION = "diffusion"  # secreted / ECM scale
ENGINES = ("liana", "commot", "stlearn")

LONG_COLS = [
    "engine", "mode", "regime", "level", "spatial",
    "ligand", "receptor", "source", "target",
    "score", "higher_better", "pvalue", "contrib_dist",
]


# ---------------------------------------------------------------------------
# 1. Load + concatenate the standardized long CSVs
# ---------------------------------------------------------------------------
def load_long(paths: list[str | Path]) -> pd.DataFrame:
    """Read and concatenate the method CSVs, tolerating missing optional cols."""
    frames = []
    for p in paths:
        if p and Path(p).exists():
            df = pd.read_csv(p)
            for c in LONG_COLS:
                if c not in df.columns:
                    df[c] = np.nan
            frames.append(df[LONG_COLS])
    if not frames:
        return pd.DataFrame(columns=LONG_COLS)
    out = pd.concat(frames, ignore_index=True)
    out["ligand"] = out["ligand"].astype(str)
    out["receptor"] = out["receptor"].astype(str)
    return out


# ---------------------------------------------------------------------------
# 2. Autocrine-spillover filter (single-cell platforms only)
# ---------------------------------------------------------------------------
def apply_autocrine_filter(
    long: pd.DataFrame,
    resolution_mode: str | None,
    median_nn: float | None,
    *,
    factor: float = 1.5,
) -> tuple[pd.DataFrame, dict]:
    """Drop segmentation-spillover autocrine calls on ``single_cell`` data.

    A segmented cell's own transcripts bleed into touching same-type neighbours,
    manufacturing false ``source==target`` calls. Distance-aware mode drops those
    whose contributing cell-pair distance is below ``factor * median_nn`` (same
    coordinate units as ``obsm['spatial']``); with no ``contrib_dist`` it drops
    ALL autocrine rows and records that. No-op on ``spot_multicell``.
    """
    diag = {"pre": int(len(long)), "post": int(len(long)),
            "applied": False, "mode": "not_applied"}
    if resolution_mode != "single_cell" or len(long) == 0:
        return long, diag
    auto = long["source"].astype(str) == long["target"].astype(str)
    have_dist = long["contrib_dist"].notna().any() and median_nn is not None
    if have_dist:
        drop = auto & (long["contrib_dist"].fillna(np.inf) < factor * float(median_nn))
        diag["mode"] = "distance_aware"
    else:
        drop = auto
        diag["mode"] = "categorical_all_autocrine"
    out = long[~drop].copy()
    diag.update(applied=True, post=int(len(out)))
    return out, diag


# ---------------------------------------------------------------------------
# 3. Within-method percentile rank
# ---------------------------------------------------------------------------
def add_rank_pct(df: pd.DataFrame) -> pd.DataFrame:
    """Percentile-rank each row within its (engine, mode, regime) group so that
    STRONGER evidence -> higher ``rank_pct`` (near 1). ``higher_better`` flips the
    direction per method (LIANA specificity_rank is lower-is-better; COMMOT
    strength and stLearn n_sig_spots are higher-is-better)."""
    df = df.copy()
    if len(df) == 0:
        df["rank_pct"] = pd.Series(dtype=float)
        return df
    hb = df["higher_better"].fillna(True).astype(bool)
    df["_strength"] = np.where(hb, df["score"], -df["score"])
    df["rank_pct"] = (
        df.groupby(["engine", "mode", "regime"])["_strength"]
        .rank(method="average", pct=True)
    )
    return df.drop(columns="_strength")


# ---------------------------------------------------------------------------
# 4. Directed cell-type consensus (per regime)
# ---------------------------------------------------------------------------
KEY = ["ligand", "receptor", "source", "target"]


def _lr_spatial_support(long: pd.DataFrame, regime: str) -> set:
    """(ligand, receptor) pairs with a LIANA bivariate hit at this regime."""
    biv = long[(long["engine"] == "liana") & (long["mode"] == "bivariate")
               & (long["regime"] == regime)]
    return set(zip(biv["ligand"], biv["receptor"]))


def consensus_regime(
    long_ranked: pd.DataFrame,
    regime: str,
    universes: dict[str, set] | None,
    *,
    min_methods: int = 2,
    require_spatial: bool = True,
) -> pd.DataFrame:
    """Consensus over cell-type triples in one spatial regime.

    The non-spatial LIANA ``rank_aggregate`` (regime ``coexpr``) is folded in as
    corroboration; ``require_spatial`` guarantees it never solely supports a row.
    """
    cols = KEY + ["engines_sig", "n_sig", "n_capable", "any_spatial",
                  "lr_spatial_support", "consensus_pct", "tier"]
    ct = long_ranked[(long_ranked["level"] == "celltype_pair")
                     & long_ranked["regime"].isin([regime, COEXPR])].copy()
    if len(ct) == 0:
        return pd.DataFrame(columns=cols)

    # One rank per (triple, engine): an engine's strongest mode in this pool.
    per_engine = (
        ct.groupby(KEY + ["engine"], as_index=False)
        .agg(rank_pct=("rank_pct", "max"), spatial=("spatial", "any"))
    )
    piv = per_engine.pivot_table(index=KEY, columns="engine",
                                 values="rank_pct", aggfunc="max")
    spat = (per_engine[per_engine["spatial"]]
            .pivot_table(index=KEY, columns="engine", values="spatial", aggfunc="any"))

    g = pd.DataFrame(index=piv.index)
    g["engines_sig"] = [sorted(piv.columns[row.notna()]) for _, row in piv.iterrows()]
    g["n_sig"] = piv.notna().sum(axis=1)
    g["consensus_pct"] = piv.mean(axis=1, skipna=True)          # higher = stronger
    g["any_spatial"] = spat.reindex(piv.index).any(axis=1).fillna(False)
    g = g.reset_index()

    lr_sup = _lr_spatial_support(long_ranked, regime)
    g["lr_spatial_support"] = [(l, r) in lr_sup for l, r in zip(g["ligand"], g["receptor"])]

    def n_capable(l, r):
        if not universes:
            return np.nan
        return int(sum((l, r) in u for u in universes.values()))
    g["n_capable"] = [n_capable(l, r) for l, r in zip(g["ligand"], g["receptor"])]

    g = g[g["n_sig"] >= min_methods]
    if require_spatial:
        g = g[g["any_spatial"] | g["lr_spatial_support"]]
    if len(g) == 0:
        return pd.DataFrame(columns=cols)
    g["tier"] = [
        _tier(ns, cp, sp) for ns, cp, sp in
        zip(g["n_sig"], g["consensus_pct"], g["any_spatial"])
    ]
    return g.sort_values(["n_sig", "consensus_pct"], ascending=[False, False])[cols] \
            .reset_index(drop=True)


def _tier(n_sig: int, consensus_pct: float, any_spatial: bool) -> str:
    if n_sig >= 2 and consensus_pct >= 0.95 and any_spatial:
        return "high"
    if n_sig >= 2 and consensus_pct >= 0.80:
        return "supported"
    return "method_specific"


def build_consensus(
    long: pd.DataFrame,
    universes: dict[str, set] | None = None,
    *,
    min_methods: int = 2,
    resolution_mode: str | None = None,
    median_nn: float | None = None,
    autocrine_factor: float = 1.5,
    require_spatial: bool = True,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Autocrine filter -> percentile rank -> per-regime consensus. Returns
    ({regime: df}, autocrine_diag)."""
    long, adiag = apply_autocrine_filter(
        long, resolution_mode, median_nn, factor=autocrine_factor)
    ranked = add_rank_pct(long)
    out = {}
    for regime in (CONTACT, DIFFUSION):
        df = consensus_regime(ranked, regime, universes,
                              min_methods=min_methods, require_spatial=require_spatial)
        for k, v in [("n_triples_pre_autocrine", adiag["pre"]),
                     ("n_triples_post_autocrine", adiag["post"]),
                     ("autocrine_filter", adiag["mode"])]:
            df[k] = v
        out[regime] = df
    return out, adiag


def high_confidence(consensus: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Shortlist: tier in {high, supported}, tagged with regime."""
    parts = []
    for regime, df in consensus.items():
        if len(df):
            sel = df[df["tier"].isin(["high", "supported"])].copy()
            sel["regime"] = regime
            parts.append(sel)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ---------------------------------------------------------------------------
# 5. Panel coverage / overlap
# ---------------------------------------------------------------------------
def panel_coverage(universes: dict[str, set]) -> tuple[pd.DataFrame, dict]:
    names = sorted(universes)
    cov = pd.DataFrame([{"method": m, "n_operable_pairs": len(universes[m])} for m in names])
    overlap = {}
    if len(names) >= 2:
        overlap["pairwise"] = {
            f"{a}&{b}": len(universes[a] & universes[b])
            for a, b in itertools.combinations(names, 2)
        }
        overlap["pairwise_jaccard"] = {
            f"{a}&{b}": round(len(universes[a] & universes[b])
                              / max(1, len(universes[a] | universes[b])), 3)
            for a, b in itertools.combinations(names, 2)
        }
        three = set.intersection(*universes.values()) if universes else set()
        overlap["three_way"] = len(three)
    return cov, overlap


def _load_universe(path: str | None) -> set:
    if not path or not Path(path).exists():
        return set()
    u = pd.read_csv(path)
    lc = next((c for c in u.columns if c.lower() in ("ligand", "ligand_gene")), u.columns[0])
    rc = next((c for c in u.columns if c.lower() in ("receptor", "receptor_gene")), u.columns[1])
    return {(str(a), str(b)) for a, b in zip(u[lc], u[rc])}


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------
def _run_cli(a: argparse.Namespace) -> None:
    long = load_long([a.liana, a.commot, a.stlearn])
    universes = {
        m: _load_universe(p) for m, p in
        {"liana": a.univ_liana, "commot": a.univ_commot, "stlearn": a.univ_stlearn}.items()
        if p and Path(p).exists()
    } or None

    consensus, adiag = build_consensus(
        long, universes, min_methods=a.min_methods,
        resolution_mode=a.resolution_mode, median_nn=a.median_nn,
        autocrine_factor=a.autocrine_factor)

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    consensus[CONTACT].to_csv(outdir / "ccc_consensus_contact.csv", index=False)
    consensus[DIFFUSION].to_csv(outdir / "ccc_consensus_diffusion.csv", index=False)
    high_confidence(consensus).to_csv(outdir / "ccc_high_confidence.csv", index=False)
    if universes:
        cov, overlap = panel_coverage(universes)
        cov.to_csv(outdir / "ccc_panel_coverage.csv", index=False)
        (outdir / "ccc_panel_overlap.json").write_text(json.dumps(overlap, indent=2))
    n = sum(len(v) for v in consensus.values())
    print(f"[ccc_aggregate] {n} consensus triples "
          f"(contact={len(consensus[CONTACT])}, diffusion={len(consensus[DIFFUSION])}); "
          f"autocrine={adiag['mode']} -> {outdir}")


def _selftest() -> None:
    """Shared-resource, single-gene pairs: LIANA(coexpr) + COMMOT(contact) +
    stLearn(contact) agree on TGFB1->TGFBR1; must unify as ONE row, 3 engines,
    with LIANA counted once and require_spatial satisfied by COMMOT/stLearn."""
    rows = [
        dict(engine="liana", mode="rank_aggregate", regime=COEXPR, level="celltype_pair",
             spatial=False, ligand="TGFB1", receptor="TGFBR1", source="A", target="B",
             score=0.01, higher_better=False, pvalue=0.01, contrib_dist=np.nan),
        dict(engine="liana", mode="rank_aggregate", regime=COEXPR, level="celltype_pair",
             spatial=False, ligand="TGFB1", receptor="TGFBR1", source="A", target="A",
             score=0.9, higher_better=False, pvalue=0.9, contrib_dist=np.nan),
        dict(engine="commot", mode="cluster", regime=CONTACT, level="celltype_pair",
             spatial=True, ligand="TGFB1", receptor="TGFBR1", source="A", target="B",
             score=5.0, higher_better=True, pvalue=0.002, contrib_dist=40.0),
        dict(engine="stlearn", mode="cci", regime=CONTACT, level="celltype_pair",
             spatial=True, ligand="TGFB1", receptor="TGFBR1", source="A", target="B",
             score=12, higher_better=True, pvalue=0.01, contrib_dist=40.0),
        # LIANA bivariate corroborates the LR pair (spatial, LR-level, no direction)
        dict(engine="liana", mode="bivariate", regime=CONTACT, level="lr",
             spatial=True, ligand="TGFB1", receptor="TGFBR1", source=np.nan, target=np.nan,
             score=0.8, higher_better=True, pvalue=0.01, contrib_dist=np.nan),
    ]
    long = pd.DataFrame(rows)
    universes = {"liana": {("TGFB1", "TGFBR1")}, "commot": {("TGFB1", "TGFBR1")},
                 "stlearn": {("TGFB1", "TGFBR1")}}
    cons, _ = build_consensus(long, universes, min_methods=2)
    c = cons[CONTACT]
    row = c[(c.source == "A") & (c.target == "B")].iloc[0]
    assert row["n_sig"] == 3 and row["n_capable"] == 3, dict(row)
    assert sorted(row["engines_sig"]) == ["commot", "liana", "stlearn"], dict(row)
    assert row["lr_spatial_support"], dict(row)
    print("PASS: 3 engines unified on shared single-gene pair; LIANA counted once.")

    # LIANA rank + bivariate on the same pair must NOT self-consensus (one engine).
    long2 = pd.DataFrame([
        dict(engine="liana", mode="rank_aggregate", regime=COEXPR, level="celltype_pair",
             spatial=False, ligand="TGFB1", receptor="TGFBR1", source="A", target="B",
             score=0.01, higher_better=False, pvalue=0.01, contrib_dist=np.nan),
        dict(engine="liana", mode="bivariate", regime=CONTACT, level="lr", spatial=True,
             ligand="TGFB1", receptor="TGFBR1", source=np.nan, target=np.nan,
             score=0.8, higher_better=True, pvalue=0.01, contrib_dist=np.nan),
    ])
    cons2, _ = build_consensus(long2, None, min_methods=2)
    assert len(cons2[CONTACT]) == 0, "LIANA's two modes must not form a 2-engine consensus"
    print("PASS: LIANA rank+bivariate alone do not self-consensus.")

    # Autocrine spillover on single_cell: A->A below 1.5*median_nn is dropped.
    long3 = pd.DataFrame([
        dict(engine="commot", mode="cluster", regime=CONTACT, level="celltype_pair",
             spatial=True, ligand="TGFB1", receptor="TGFBR1", source="A", target="A",
             score=5.0, higher_better=True, pvalue=0.002, contrib_dist=10.0),
        dict(engine="stlearn", mode="cci", regime=CONTACT, level="celltype_pair",
             spatial=True, ligand="TGFB1", receptor="TGFBR1", source="A", target="A",
             score=12, higher_better=True, pvalue=0.01, contrib_dist=10.0),
    ])
    cons3, ad = build_consensus(long3, None, min_methods=2,
                                resolution_mode="single_cell", median_nn=100.0)
    assert ad["mode"] == "distance_aware" and len(cons3[CONTACT]) == 0, (ad, cons3[CONTACT])
    print("PASS: single-cell autocrine spillover (dist < 1.5*median_nn) dropped.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selftest", action="store_true", help="run self-tests and exit")
    p.add_argument("--liana", help="liana_ccc.csv (standardized long)")
    p.add_argument("--commot", help="commot_ccc.csv")
    p.add_argument("--stlearn", help="stlearn_ccc.csv")
    p.add_argument("--univ-liana", help="liana_universe.csv (ligand,receptor)")
    p.add_argument("--univ-commot", help="commot_universe.csv")
    p.add_argument("--univ-stlearn", help="stlearn_universe.csv")
    p.add_argument("--resolution-mode", choices=["spot_multicell", "single_cell"],
                   help="from logs/ccc_data_prep.json; enables autocrine filter on single_cell")
    p.add_argument("--median-nn", type=float,
                   help="median_nn in obsm['spatial'] units (autocrine threshold)")
    p.add_argument("--autocrine-factor", type=float, default=1.5)
    p.add_argument("--min-methods", type=int, default=2)
    p.add_argument("--out", default=".", help="output directory")
    a = p.parse_args()
    if a.selftest:
        _selftest()
        return
    _run_cli(a)


if __name__ == "__main__":
    main()
