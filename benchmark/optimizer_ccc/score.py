"""Score one agent run's ensemble table against the expert reference.

Accuracy = agreement with the reference run of the same frozen scripts on the
same input: Spearman rank correlation of ``ensemble_score`` over the common
(ligand, receptor) universe, plus Jaccard overlap of the top-k sets. A
structurally broken output (missing file / columns / empty) is invalid and
scores nothing — validity is its own round-level metric (valid-run rate).
"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_COLUMNS = [
    "ligand", "receptor",
    "liana_score", "commot_score", "stlearn_score", "decoupler_score",
    "liana_pct", "commot_pct", "stlearn_pct", "decoupler_pct",
    "ensemble_score",
]


def score_run(agent_csv: Path, reference_csv: Path, k: int = 20) -> dict:
    result = {
        "valid": False, "reason": None, "n_agent": 0, "n_reference": 0,
        "n_common": 0, "spearman": None, "topk_jaccard": None, "k": k,
    }
    import pandas as pd
    from scipy.stats import spearmanr

    agent_csv, reference_csv = Path(agent_csv), Path(reference_csv)
    if not agent_csv.is_file():
        result["reason"] = f"missing file: {agent_csv}"
        return result
    try:
        agent = pd.read_csv(agent_csv)
    except Exception as e:
        result["reason"] = f"unparseable csv: {e}"
        return result
    missing = [c for c in REQUIRED_COLUMNS if c not in agent.columns]
    if missing:
        result["reason"] = f"missing columns: {missing}"
        return result
    if agent.empty:
        result["reason"] = "empty table"
        return result

    reference = pd.read_csv(reference_csv)
    result["valid"] = True
    result["n_agent"] = int(len(agent))
    result["n_reference"] = int(len(reference))

    def keyed(df):
        df = df.copy()
        df["_key"] = df["ligand"].astype(str).str.upper() + "|" + df["receptor"].astype(str).str.upper()
        return df.drop_duplicates("_key").set_index("_key")

    a, r = keyed(agent), keyed(reference)
    common = a.index.intersection(r.index)
    result["n_common"] = int(len(common))
    if len(common) >= 3:
        rho, _ = spearmanr(a.loc[common, "ensemble_score"], r.loc[common, "ensemble_score"])
        result["spearman"] = None if rho != rho else round(float(rho), 4)  # NaN-safe

    top_a = set(a.sort_values("ensemble_score", ascending=False).head(k).index)
    top_r = set(r.sort_values("ensemble_score", ascending=False).head(k).index)
    if top_a or top_r:
        result["topk_jaccard"] = round(len(top_a & top_r) / len(top_a | top_r), 4)
    return result


def tokens_from_metrics(metrics_path: Path) -> dict:
    """Extract the run's token cost from a metrics.json (empty dict if absent)."""
    metrics_path = Path(metrics_path)
    if not metrics_path.is_file():
        return {}
    m = json.loads(metrics_path.read_text())
    usage = m.get("usage") or {}
    loops = m.get("loops") or {}
    return {
        "total_tokens": usage.get("total_tokens"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "llm_calls": usage.get("llm_calls"),
        "replans": loops.get("replans_triggered"),
        "terminal_state": (m.get("outcome") or {}).get("terminal_state"),
        "wall_time_s": (m.get("run") or {}).get("wall_time_s"),
    }


def aggregate_round(per_run: list[dict]) -> dict:
    """Round-level aggregates over per-run score dicts (with tokens merged in)."""
    n = len(per_run)
    valid = [r for r in per_run if r.get("valid")]
    spearmans = [r["spearman"] for r in valid if r.get("spearman") is not None]
    jaccards = [r["topk_jaccard"] for r in valid if r.get("topk_jaccard") is not None]
    tokens = sorted(r["total_tokens"] for r in per_run if r.get("total_tokens") is not None)
    return {
        "n_runs": n,
        "valid_run_rate": round(len(valid) / n, 3) if n else None,
        "mean_spearman": round(sum(spearmans) / len(spearmans), 4) if spearmans else None,
        "mean_topk_jaccard": round(sum(jaccards) / len(jaccards), 4) if jaccards else None,
        "median_total_tokens": tokens[len(tokens) // 2] if tokens else None,
    }
