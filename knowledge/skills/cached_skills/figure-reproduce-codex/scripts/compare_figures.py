#!/usr/bin/env python3
"""Compare a reproduction with its reference and emit hash-bound metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment
from skimage.color import deltaE_ciede2000, rgb2gray, rgb2lab
from skimage.metrics import structural_similarity


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _square(image: Image.Image, size: int = 512) -> np.ndarray:
    return np.asarray(image.resize((size, size), Image.Resampling.BILINEAR), dtype=float) / 255


def _background(array: np.ndarray) -> np.ndarray:
    return np.median(np.concatenate((array[0], array[-1], array[:, 0], array[:, -1])), axis=0)


def _content_bbox(array: np.ndarray, background: np.ndarray) -> list[float] | None:
    mask = np.max(np.abs(array.astype(float) - background), axis=2) >= 12
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    height, width = mask.shape
    return [
        round(xs.min() / width, 4),
        round(ys.min() / height, 4),
        round(xs.max() / width, 4),
        round(ys.max() / height, 4),
    ]


def _palette(image: Image.Image, count: int = 12) -> tuple[np.ndarray, np.ndarray]:
    quantized = image.convert("RGB").quantize(colors=count, method=Image.Quantize.MEDIANCUT)
    color_counts = quantized.getcolors(maxcolors=count) or []
    palette = np.asarray(quantized.getpalette(), dtype=float).reshape(-1, 3)
    counts = np.array([value[0] for value in color_counts], dtype=float)
    rgb = np.array([palette[value[1]] for value in color_counts], dtype=float)
    return rgb, counts / counts.sum()


def _palette_delta(left: Image.Image, right: Image.Image) -> float | None:
    left_rgb, left_weight = _palette(left)
    right_rgb, right_weight = _palette(right)
    if not len(left_rgb) or not len(right_rgb):
        return None
    left_lab = rgb2lab((left_rgb / 255).reshape((-1, 1, 3))).reshape((-1, 3))
    right_lab = rgb2lab((right_rgb / 255).reshape((-1, 1, 3))).reshape((-1, 3))
    distances = deltaE_ciede2000(left_lab[:, None, :], right_lab[None, :, :])
    rows, columns = linear_sum_assignment(distances)
    weights = np.minimum(left_weight[rows], right_weight[columns])
    return float(np.average(distances[rows, columns], weights=weights))


def _side_by_side(
    left: Image.Image, right: Image.Image, path: Path, letterbox: bool = False
) -> None:
    if letterbox:
        cell_width, cell_height = max(left.width, right.width), max(left.height, right.height)

        def fit(image):
            scale = min(cell_width / image.width, cell_height / image.height)
            resized = image.resize((round(image.width * scale), round(image.height * scale)))
            cell = Image.new("RGB", (cell_width, cell_height), (128, 128, 128))
            cell.paste(
                resized, ((cell_width - resized.width) // 2, (cell_height - resized.height) // 2)
            )
            return cell

        panels = [fit(left), fit(right)]
    else:
        height = max(left.height, right.height)
        panels = [
            image.resize((round(image.width * height / image.height), height))
            for image in (left, right)
        ]
        cell_width, cell_height = panels[0].width, height
    canvas = Image.new("RGB", (panels[0].width + panels[1].width + 10, panels[0].height), "white")
    canvas.paste(panels[0], (0, 0))
    canvas.paste(panels[1], (panels[0].width + 10, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def compare(
    original_path: str | Path,
    reproduced_path: str | Path,
    diff_path: str | Path | None = None,
    geometry_path: str | Path | None = None,
) -> dict:
    """Compute hash-bound structural, color, and geometry evidence."""
    original_path, reproduced_path = Path(original_path), Path(reproduced_path)
    original = Image.open(original_path).convert("RGB")
    reproduced = Image.open(reproduced_path).convert("RGB")
    original_array, reproduced_array = np.asarray(original), np.asarray(reproduced)
    original_square, reproduced_square = _square(original), _square(reproduced)
    gray_original, gray_reproduced = rgb2gray(original_square), rgb2gray(reproduced_square)
    ssim = float(structural_similarity(gray_original, gray_reproduced, data_range=1.0))
    transforms = {
        "identity": reproduced_square,
        "flip_x": np.fliplr(reproduced_square),
        "flip_y": np.flipud(reproduced_square),
        "rotate_180": np.flipud(np.fliplr(reproduced_square)),
    }
    orientation_scores = {
        name: float(structural_similarity(gray_original, rgb2gray(value), data_range=1.0))
        for name, value in transforms.items()
    }
    best_orientation = max(orientation_scores, key=orientation_scores.get)
    original_bg, reproduced_bg = _background(original_array), _background(reproduced_array)
    background_delta = float(np.linalg.norm(original_bg - reproduced_bg))
    original_aspect = original.width / original.height
    reproduced_aspect = reproduced.width / reproduced.height
    aspect_error = abs(reproduced_aspect / original_aspect - 1)
    findings = []
    if aspect_error > 0.03:
        findings.append(f"canvas aspect differs by {aspect_error:.1%}")
    if background_delta > 15:
        findings.append(f"background RGB distance is {background_delta:.1f}")
    if best_orientation != "identity" and orientation_scores[best_orientation] >= ssim + 0.03:
        improvement = orientation_scores[best_orientation] - ssim
        findings.append(
            f"orientation candidate {best_orientation} improves SSIM by {improvement:.3f}"
        )
    palette_delta = _palette_delta(original, reproduced)
    metrics = {
        "inputs": {
            "original": str(original_path),
            "reproduced": str(reproduced_path),
            "original_sha256": _hash(original_path),
            "reproduced_sha256": _hash(reproduced_path),
        },
        "ssim": round(ssim, 4),
        "palette_mean_delta_e": None if palette_delta is None else round(palette_delta, 2),
        "pass2_geometry": {
            "canvas_original": {
                "size": list(original.size),
                "aspect": round(original_aspect, 4),
                "background_rgb": original_bg.round().astype(int).tolist(),
                "content_bbox": _content_bbox(original_array, original_bg),
            },
            "canvas_reproduced": {
                "size": list(reproduced.size),
                "aspect": round(reproduced_aspect, 4),
                "background_rgb": reproduced_bg.round().astype(int).tolist(),
                "content_bbox": _content_bbox(reproduced_array, reproduced_bg),
            },
            "orientation_scores": {
                key: round(value, 4) for key, value in orientation_scores.items()
            },
            "findings": findings,
            "clean": not findings,
        },
    }
    if diff_path:
        _side_by_side(original, reproduced, Path(diff_path))
    if geometry_path:
        _side_by_side(original, reproduced, Path(geometry_path), letterbox=True)
    return metrics


def main() -> int:
    """Run the figure comparison CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original")
    parser.add_argument("reproduced")
    parser.add_argument("--out", required=True)
    parser.add_argument("--geometry-out", required=True)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()
    metrics = compare(args.original, args.reproduced, args.out, args.geometry_out)
    Path(args.json_out).write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
