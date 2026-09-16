"""Spatial label maps and metric plots for the tissue-niche agent study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import anndata as ad
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from .evaluation import load_predictions, load_study, load_truth
from .protocol import UNMATCHED, sha256, write_json

METHOD_NAMES = {"tissueagent": "TissueAgent", "biomni": "Biomni", "spatialagent": "SpatialAgent"}
METHOD_COLORS = {"tissueagent": "#4477AA", "biomni": "#EE9944", "spatialagent": "#228833"}
DATASET_NAMES = {
    "developing_human_heart": "Developing human heart",
    "ovca_xenium_spatialfusion": "Ovarian cancer (Xenium)",
}


def label_palette(labels: list[str]) -> dict:
    """Assign a stable color to each label in the dataset contract."""
    cmap = plt.get_cmap("tab10" if len(labels) <= 9 else "tab20")
    gray_indices = {7} if cmap.N == 10 else {14, 15}
    colors = [matplotlib.colors.to_hex(cmap(i)) for i in range(cmap.N) if i not in gray_indices]
    return {
        **{label: colors[i % len(colors)] for i, label in enumerate(labels)},
        UNMATCHED: "#777777",
        "Unscored truth": "#dddddd",
    }


def plot_performance(study_dir: Path, output_dir: Path) -> list[Path]:
    """Redraw performance from saved metrics without expression or model environments."""
    evaluation_dir = study_dir / "evaluation"
    provenance = json.loads((evaluation_dir / "evaluation.json").read_text())
    if sha256(evaluation_dir / "metrics.tsv") != provenance["metrics_sha256"]:
        raise ValueError("Saved metrics were modified.")
    metrics = pd.read_csv(evaluation_dir / "metrics.tsv", sep="\t")
    datasets = metrics["dataset"].unique()
    figure, axes = plt.subplots(len(datasets), 2, figsize=(10, 4 * len(datasets)), squeeze=False)
    for row, dataset in enumerate(datasets):
        data = metrics[metrics["dataset"] == dataset]
        conditions = data[["method", "model"]].drop_duplicates().itertuples(index=False, name=None)
        conditions = list(conditions)
        for column, metric in enumerate(("macro_f1", "balanced_accuracy")):
            ax = axes[row, column]
            tick_labels = []
            for position, (method, model) in enumerate(conditions):
                runs = data[(data["method"] == method) & (data["model"] == model)]
                values = runs[metric].dropna().to_numpy()
                complete = int((runs["status"] == "success").sum())
                tick_labels.append(
                    f"{METHOD_NAMES[method]}\n{model}\n{complete}/{len(runs)} complete"
                )
                if len(values):
                    ax.bar(
                        position,
                        values.mean(),
                        color=METHOD_COLORS[method],
                        alpha=0.8,
                        yerr=values.std(ddof=1) if len(values) > 1 else None,
                        capsize=4,
                    )
                    offsets = np.linspace(-0.08, 0.08, len(values)) if len(values) > 1 else 0
                    ax.scatter(
                        position + offsets,
                        values,
                        color="black",
                        s=20,
                        zorder=3,
                    )
                else:
                    ax.text(position, 0.04, "No result", ha="center", rotation=90)
            ax.set(
                xticks=range(len(conditions)),
                xticklabels=tick_labels,
                ylim=(0, 1.05),
                title=f"{DATASET_NAMES.get(dataset, dataset)}\n{metric.replace('_', ' ').title()}",
            )
            ax.spines[["top", "right"]].set_visible(False)
    figure.suptitle(
        "Mean ± SD across runs; dots show individual runs\n"
        "Completion counts refer to full workflows",
        fontsize=11,
    )
    figure.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for extension in ("png", "pdf"):
        path = output_dir / f"performance.{extension}"
        figure.savefig(path, dpi=250, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)
    return paths


def plot_spatial(study_dir: Path, output_dir: Path, *, seed: int | None = None) -> list[Path]:
    """Plot ground truth and all methods with identical per-section coordinates and colors."""
    study = load_study(study_dir)
    seed = study["config"]["seeds"][0] if seed is None else seed
    if seed not in study["config"]["seeds"]:
        raise ValueError("Requested seed is absent from the study.")
    entries = {(e["dataset"], e["method"], e["seed"], e["section_id"]): e for e in study["runs"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    paths, palettes = [], {}
    methods = study["config"]["methods"]
    panel_seeds = {}
    for method in methods:
        available = study["config"].get(method, {}).get("seeds", study["config"]["seeds"])
        panel_seeds[method] = (
            seed if seed in available else available[0] if len(available) == 1 else None
        )
    for dataset, prepared in study["preparations"].items():
        truth = load_truth(prepared)
        palette = label_palette(prepared["sections"][0]["contract"]["labels"])
        palettes[dataset] = palette
        for section in prepared["sections"]:
            if sha256(section["query_h5ad"]) != section["query_sha256"]:
                raise ValueError("Spatial query was modified.")
            data = ad.read_h5ad(section["query_h5ad"], backed="r")
            coords, ids = np.asarray(data.obsm["spatial"]), data.obs_names.copy()
            data.file.close()
            local_truth = truth.loc[ids]
            panels = [
                (
                    "Ground truth",
                    local_truth["ground_truth"].where(local_truth["scored"], "Unscored truth"),
                )
            ]
            for method in methods:
                method_seed = panel_seeds[method]
                entry = entries.get((dataset, method, method_seed, section["section_id"]))
                prediction = load_predictions(study_dir, entry, section, ids) if entry else None
                status = (
                    entry["status"]
                    if entry
                    else "pending"
                    if method_seed is not None
                    else "not scheduled"
                )
                panels.append(
                    (f"{METHOD_NAMES[method]} · seed {method_seed} ({status})", prediction)
                )
            figure, axes = plt.subplots(
                1,
                len(panels),
                figsize=(4.5 * len(panels), 5),
                sharex=True,
                sharey=True,
                squeeze=False,
            )
            for ax, (title, values) in zip(axes[0], panels, strict=True):
                if values is not None:
                    ax.scatter(
                        coords[:, 0],
                        coords[:, 1],
                        c=values.map(palette),
                        s=0.5,
                        linewidths=0,
                        rasterized=True,
                    )
                else:
                    ax.text(0.5, 0.5, "No prediction artifact", ha="center", transform=ax.transAxes)
                ax.set_title(title)
                ax.set_aspect("equal")
                ax.set_axis_off()
            handles = [
                Line2D([], [], marker="o", linestyle="", color=color, label=label)
                for label, color in palette.items()
            ]
            figure.legend(handles=handles, loc="lower center", ncol=min(5, len(handles)))
            figure.suptitle(f"{dataset} · {section['section_id']} · seed {seed}")
            figure.tight_layout(rect=(0, 0.15, 1, 0.94))
            for extension in ("png", "pdf"):
                path = output_dir / f"{dataset}-{section['section_id']}-seed-{seed}.{extension}"
                figure.savefig(path, dpi=250, bbox_inches="tight")
                paths.append(path)
            plt.close(figure)
    write_json(
        output_dir / f"spatial-seed-{seed}.json",
        {
            "study_manifest_sha256": sha256(study_dir / "study_manifest.json"),
            "seed": seed,
            "method_seeds": panel_seeds,
            "palettes": palettes,
            "files": [str(path) for path in paths],
        },
    )
    return paths


def main() -> None:
    """Render performance and, optionally, spatial figures from archived outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--performance-only", action="store_true")
    args = parser.parse_args()
    output = args.output_dir or args.study_dir / "figures"
    paths = plot_performance(args.study_dir, output)
    if not args.performance_only:
        paths.extend(plot_spatial(args.study_dir, output, seed=args.seed))
    print("\n".join(map(str, paths)))


if __name__ == "__main__":
    main()
