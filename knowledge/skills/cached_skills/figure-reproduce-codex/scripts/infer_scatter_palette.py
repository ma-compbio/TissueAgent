#!/usr/bin/env python3
"""Infer unresolved categorical-scatter colors from registered reference pixels."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor
from scipy.cluster.vq import kmeans2
from skimage.color import deltaE_ciede2000, rgb2lab


@dataclass
class InferenceResult:
    """Accepted inferences, registration evidence, and unresolved labels."""

    inferred: dict[str, dict]
    registration: dict
    unresolved: list[str]


def merge_provenance(partial: dict, inference: InferenceResult) -> dict:
    """Merge accepted pixel evidence into partial colormap provenance."""
    mapping = dict(partial.get("mapping", {}))
    provenance = dict(partial.get("provenance", {}))
    for label, evidence in inference.inferred.items():
        mapping[label] = evidence["hex"]
        provenance[label] = dict(evidence)
    return {
        "mapping": mapping,
        "provenance": provenance,
        "unresolved_dataset_labels": list(inference.unresolved),
        "unused_reference_labels": list(partial.get("unused_reference_labels", [])),
        "registration": inference.registration,
        "status": "resolved" if not inference.unresolved else "unresolved dataset labels",
    }


def _lab(rgb: np.ndarray) -> np.ndarray:
    array = np.asarray(rgb, dtype=float) / 255.0
    return rgb2lab(array.reshape((-1, 1, 3))).reshape((-1, 3))


def delta_e_hex(left: str, right: str) -> float:
    """Return CIEDE2000 distance between two hexadecimal colors."""
    values = np.array([ImageColor.getrgb(left), ImageColor.getrgb(right)])
    labs = _lab(values)
    return float(_delta_e(labs[0], labs[1]))


def _delta_e(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left, right = np.asarray(left), np.asarray(right)
    shape = np.broadcast_shapes(left.shape, right.shape)
    return deltaE_ciede2000(np.broadcast_to(left, shape), np.broadcast_to(right, shape))


def _mapped_points(
    coordinates: np.ndarray,
    box: tuple[int, int, int, int],
    swap: bool,
    flip_x: bool,
    flip_y: bool,
    offset_x: int,
    offset_y: int,
    padding: float,
) -> np.ndarray:
    values = coordinates[:, ::-1] if swap else coordinates.copy()
    low = np.nanmin(values, axis=0)
    high = np.nanmax(values, axis=0)
    span = np.maximum(high - low, 1e-12)
    low = low - padding * span
    high = high + padding * span
    normalized = (values - low) / (high - low)
    if flip_x:
        normalized[:, 0] = 1 - normalized[:, 0]
    if flip_y:
        normalized[:, 1] = 1 - normalized[:, 1]
    x0, y0, x1, y1 = box
    return np.column_stack(
        (
            x0 + normalized[:, 0] * (x1 - x0) + offset_x,
            y0 + normalized[:, 1] * (y1 - y0) + offset_y,
        )
    )


def _patch_pixels(image: np.ndarray, point: np.ndarray, radius: int = 2) -> np.ndarray:
    x, y = np.rint(point).astype(int)
    x0, x1 = max(0, x - radius), min(image.shape[1], x + radius + 1)
    y0, y1 = max(0, y - radius), min(image.shape[0], y + radius + 1)
    return image[y0:y1, x0:x1].reshape(-1, 3)


def _registration_score(
    image_lab: np.ndarray,
    points: np.ndarray,
    categories: np.ndarray,
    known_palette: dict[str, str],
) -> float:
    expected = {
        key: _lab(np.array([ImageColor.getrgb(value)]))[0] for key, value in known_palette.items()
    }
    indices = np.array([index for index, category in enumerate(categories) if category in expected])
    if not len(indices):
        return 0.0
    if len(indices) > 400:
        indices = indices[np.linspace(0, len(indices) - 1, 400, dtype=int)]
    selected = points[indices]
    targets = np.array([expected[categories[index]] for index in indices])
    xs = np.rint(selected[:, 0]).astype(int)
    ys = np.rint(selected[:, 1]).astype(int)
    best = np.full(len(indices), np.inf)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            sample = image_lab[
                np.clip(ys + dy, 0, image_lab.shape[0] - 1),
                np.clip(xs + dx, 0, image_lab.shape[1] - 1),
            ]
            best = np.minimum(best, _delta_e(sample, targets))
    return float(np.mean(best <= 12))


def infer_palette(
    reference: str | Path,
    coordinates: np.ndarray,
    categories: np.ndarray,
    known_palette: dict[str, str],
    unresolved: list[str],
    plot_box: tuple[int, int, int, int],
) -> InferenceResult:
    """Infer missing colors only after registering known categorical points."""
    image = np.asarray(Image.open(reference).convert("RGB"))
    image_lab = rgb2lab(image.astype(float) / 255)
    candidates = []
    for swap in (False, True):
        for flip_x in (False, True):
            for flip_y in (False, True):
                for padding in (0.0, 0.015, 0.03, 0.05, 0.1):
                    for offset_x in range(-6, 7, 2):
                        for offset_y in range(-6, 7, 2):
                            points = _mapped_points(
                                coordinates,
                                plot_box,
                                swap,
                                flip_x,
                                flip_y,
                                offset_x,
                                offset_y,
                                padding,
                            )
                            score = _registration_score(
                                image_lab, points, categories, known_palette
                            )
                            candidates.append(
                                (score, swap, flip_x, flip_y, offset_x, offset_y, padding, points)
                            )
    score, swap, flip_x, flip_y, offset_x, offset_y, padding, points = max(
        candidates, key=lambda item: item[0]
    )
    registration = {
        "accepted": score >= 0.2,
        "match_rate": round(float(score), 4),
        "swap_axes": swap,
        "flip_x": flip_x,
        "flip_y": flip_y,
        "offset": [offset_x, offset_y],
        "coordinate_padding": padding,
        "delta_e_threshold": 12,
    }
    if not registration["accepted"]:
        return InferenceResult({}, registration, list(unresolved))

    known_labs = _lab(np.array([ImageColor.getrgb(value) for value in known_palette.values()]))
    background = np.median(np.concatenate((image[0], image[-1], image[:, 0], image[:, -1])), axis=0)
    background_lab = _lab(np.array([background]))[0]
    rounded = np.rint(points).astype(int)
    center_rgb = image[
        np.clip(rounded[:, 1], 0, image.shape[0] - 1),
        np.clip(rounded[:, 0], 0, image.shape[1] - 1),
    ]
    center_labs = _lab(center_rgb)
    inferred = {}
    remaining = []
    for label in unresolved:
        indices = np.flatnonzero(categories == label)
        label_labs = center_labs[indices]
        label_rgb = center_rgb[indices]
        eligible = (_delta_e(label_labs, background_lab) >= 7) & (
            np.min(_delta_e(label_labs[:, None, :], known_labs[None, :, :]), axis=1) >= 6
        )
        candidate_labs = label_labs[eligible]
        if len(candidate_labs) < 25:
            remaining.append(label)
            continue
        unique_bins = len(np.unique(np.round(candidate_labs, 1), axis=0))
        cluster_count = min(unique_bins, 16, max(4, len(candidate_labs) // 100))
        centroids, _ = kmeans2(candidate_labs, cluster_count, minit="++", seed=0)
        comparison_labs = center_labs[~np.isin(categories, unresolved)]
        ranked = []
        for centroid in centroids:
            support = _delta_e(label_labs, centroid) <= 8
            count = int(support.sum())
            coverage = count / max(1, len(indices))
            comparison_rate = (
                float(np.mean(_delta_e(comparison_labs, centroid) <= 8))
                if len(comparison_labs)
                else 0.0
            )
            agreement = coverage / max(coverage + comparison_rate, 1e-12)
            separation = float(np.min(_delta_e(known_labs, centroid)))
            if count >= 25 and coverage >= 0.1 and agreement >= 0.5 and separation >= 6:
                ranked.append((agreement, coverage, separation, support))
        if not ranked:
            remaining.append(label)
            continue
        agreement, coverage, separation, support = max(ranked, key=lambda item: item[:3])
        supported_labs = label_labs[support]
        centroid = np.median(supported_labs, axis=0)
        rng = np.random.default_rng(0)
        bootstrap = np.array(
            [
                np.median(
                    supported_labs[rng.integers(0, len(supported_labs), len(supported_labs))],
                    axis=0,
                )
                for _ in range(100)
            ]
        )
        stability = float(np.percentile(_delta_e(bootstrap, centroid), 95))
        if stability > 5:
            remaining.append(label)
            continue
        winner_rgb = np.median(label_rgb[support], axis=0).round().astype(int)
        color = "#" + "".join(f"{int(value):02x}" for value in winner_rgb)
        confidence = min(
            score / 0.2, coverage / 0.1, agreement / 0.5, 5 / max(stability, 1e-6), separation / 6
        )
        inferred[label] = {
            "hex": color,
            "source": "registered-reference-pixels",
            "confidence": round(float(min(confidence, 0.99)), 3),
            "samples": int(support.sum()),
            "coverage": round(float(coverage), 3),
            "cluster_agreement": round(float(agreement), 3),
            "bootstrap_delta_e_95": round(stability, 3),
            "known_color_separation_delta_e": round(separation, 3),
        }
    return InferenceResult(inferred, registration, remaining)


def _box(value: str) -> tuple[int, int, int, int]:
    values = tuple(int(item) for item in value.split(","))
    if len(values) != 4:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return values


def _load_points(
    path: Path, category_key: str, spatial_key: str, x_key: str | None, y_key: str | None
) -> tuple[np.ndarray, np.ndarray]:
    if path.suffix.lower() == ".h5ad":
        import anndata

        dataset = anndata.read_h5ad(path, backed="r")
        return np.asarray(dataset.obsm[spatial_key]), dataset.obs[category_key].astype(
            str
        ).to_numpy()
    if not x_key or not y_key:
        raise ValueError("CSV input requires --x and --y")
    import pandas as pd

    frame = pd.read_csv(path)
    return frame[[x_key, y_key]].to_numpy(float), frame[category_key].astype(str).to_numpy()


def _write_yaml(path: Path, mapping: dict[str, str]) -> None:
    lines = [f"{json.dumps(label)}: {color}" for label, color in mapping.items()]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    """Run the registered scatter-palette CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--dataset", "--points", dest="dataset", required=True)
    parser.add_argument("--x")
    parser.add_argument("--y")
    parser.add_argument("--spatial-key", default="spatial")
    parser.add_argument("--category", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--plot-box", type=_box, required=True)
    parser.add_argument("--inference-out", required=True)
    parser.add_argument("--colormap-out", required=True)
    parser.add_argument("--provenance-out", required=True)
    args = parser.parse_args()
    coordinates, categories = _load_points(
        Path(args.dataset), args.category, args.spatial_key, args.x, args.y
    )
    partial = json.loads(Path(args.provenance).read_text())
    result = infer_palette(
        args.reference,
        coordinates,
        categories,
        partial.get("mapping", {}),
        partial.get("unresolved_dataset_labels", []),
        args.plot_box,
    )
    Path(args.inference_out).write_text(
        json.dumps(
            {
                "inferred": result.inferred,
                "registration": result.registration,
                "unresolved": result.unresolved,
            },
            indent=2,
        )
        + "\n"
    )
    merged = merge_provenance(partial, result)
    Path(args.provenance_out).write_text(json.dumps(merged, indent=2) + "\n")
    if result.unresolved:
        return 2
    _write_yaml(Path(args.colormap_out), merged["mapping"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
