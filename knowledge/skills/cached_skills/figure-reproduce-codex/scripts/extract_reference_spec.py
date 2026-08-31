#!/usr/bin/env python3
"""Extract an auditable visual specification from a reference figure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def _hex(rgb: np.ndarray) -> str:
    return "#" + "".join(f"{int(value):02x}" for value in rgb)


def _components(rgb: np.ndarray) -> list[dict]:
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    background = np.median(border, axis=0)
    mask = np.max(np.abs(rgb.astype(float) - background), axis=2) >= 7
    labels, count = ndimage.label(mask)
    objects = ndimage.find_objects(labels)
    components = []
    limit = max(48, round(min(rgb.shape[:2]) * 0.25))
    for index, slices in enumerate(objects, start=1):
        if slices is None:
            continue
        ys, xs = slices
        width, height = xs.stop - xs.start, ys.stop - ys.start
        pixels = labels[ys, xs] == index
        area = int(pixels.sum())
        fill = area / max(1, width * height)
        if not (5 <= width <= limit and 5 <= height <= limit):
            continue
        if not (0.55 <= width / height <= 1.8 and area >= 20 and fill >= 0.25):
            continue
        components.append(
            {
                "x0": xs.start,
                "y0": ys.start,
                "x1": xs.stop,
                "y1": ys.stop,
                "width": width,
                "height": height,
                "area": area,
                "fill": fill,
                "pixels": pixels,
            }
        )
    return components


def _similar_group(seed: dict, components: list[dict]) -> list[dict]:
    return [
        item
        for item in components
        if abs(item["width"] - seed["width"]) <= max(2, seed["width"] * 0.25)
        and abs(item["height"] - seed["height"]) <= max(2, seed["height"] * 0.25)
    ]


def _bin(items: list[dict], axis: str, tolerance: float) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for item in sorted(items, key=lambda value: value[axis]):
        center = item[axis]
        for group in groups:
            if abs(center - np.median([entry[axis] for entry in group])) <= tolerance:
                group.append(item)
                break
        else:
            groups.append([item])
    return groups


def _pattern(items: list[dict]) -> tuple[str, list[dict], float]:
    if len(items) < 2:
        return "unknown", [], 0.0
    width = float(np.median([item["width"] for item in items]))
    height = float(np.median([item["height"] for item in items]))
    for item in items:
        item["cx"] = (item["x0"] + item["x1"] - 1) / 2
        item["cy"] = (item["y0"] + item["y1"] - 1) / 2
    columns = _bin(items, "cx", max(3.0, width * 0.45))
    rows = _bin(items, "cy", max(3.0, height * 0.45))
    vertical = max(columns, key=len)
    horizontal = max(rows, key=len)
    if len(vertical) >= max(2, round(0.65 * len(items))):
        chosen, layout = vertical, "vertical"
    elif len(horizontal) >= max(2, round(0.65 * len(items))):
        chosen, layout = horizontal, "horizontal"
    else:
        populated_rows = [row for row in rows if len(row) >= 2]
        populated_columns = [column for column in columns if len(column) >= 2]
        grid_items = {
            id(item): item for group in populated_rows + populated_columns for item in group
        }
        if len(populated_rows) >= 2 and len(populated_columns) >= 2 and len(grid_items) >= 4:
            chosen, layout = list(grid_items.values()), "grid"
        else:
            return "unknown", [], 0.0
    size_cv = np.std([item["width"] + item["height"] for item in chosen]) / max(1, width + height)
    confidence = float(np.clip(0.82 + 0.03 * min(len(chosen), 5) - size_cv, 0, 0.99))
    return layout, chosen, confidence


def find_legend_swatches(
    image: Image.Image, box: tuple[int, int, int, int]
) -> tuple[list[dict], str, float]:
    """Return repeated compact legend marks in inferred reading order."""
    crop = np.asarray(image.crop(box).convert("RGB"))
    components = _components(crop)
    candidates: list[tuple[tuple[int, float, float], str, list[dict], float]] = []
    seen: set[tuple[int, ...]] = set()
    for seed in components:
        group = _similar_group(seed, components)
        layout, chosen, confidence = _pattern(group)
        key = tuple(sorted(id(item) for item in chosen))
        if not chosen or key in seen:
            continue
        seen.add(key)
        median_area = float(np.median([item["area"] for item in chosen]))
        candidates.append(
            ((len(chosen) * median_area, median_area, confidence), layout, chosen, confidence)
        )
    if not candidates:
        return [], "unknown", 0.0
    _, layout, chosen, confidence = max(candidates, key=lambda item: item[0])
    if layout == "vertical":
        chosen.sort(key=lambda item: item["cy"])
    elif layout == "horizontal":
        chosen.sort(key=lambda item: item["cx"])
    else:
        row_tolerance = max(3.0, np.median([item["height"] for item in chosen]) * 0.6)
        rows = _bin(chosen, "cy", row_tolerance)
        chosen = [
            item
            for row in sorted(rows, key=lambda row: np.median([i["cy"] for i in row]))
            for item in sorted(row, key=lambda i: i["cx"])
        ]

    entries = []
    x_offset, y_offset = box[0], box[1]
    for item in chosen:
        patch = crop[item["y0"] : item["y1"], item["x0"] : item["x1"]]
        center = patch[
            max(0, patch.shape[0] // 2 - 2) : patch.shape[0] // 2 + 3,
            max(0, patch.shape[1] // 2 - 2) : patch.shape[1] // 2 + 3,
        ]
        rgb = np.median(center.reshape(-1, 3), axis=0).round().astype(int)
        entries.append(
            {
                "label": None,
                "hex": _hex(rgb),
                "rgb": rgb.tolist(),
                "box": [
                    item["x0"] + x_offset,
                    item["y0"] + y_offset,
                    item["x1"] + x_offset,
                    item["y1"] + y_offset,
                ],
                "method": "repeated-connected-component",
                "confidence": round(confidence, 3),
            }
        )
    return entries, layout, confidence


def extract_spec(
    image_path: str | Path,
    legend_box: tuple[int, int, int, int] | None = None,
) -> dict:
    """Measure canvas and legend evidence from a reference image."""
    image_path = Path(image_path)
    image = Image.open(image_path).convert("RGB")
    if legend_box is None:
        width, height = image.size
        boxes = [
            (round(width * 0.45), 0, width, height),
            (0, round(height * 0.65), width, height),
            (round(width * 0.5), 0, width, round(height * 0.6)),
        ]
        results = [(find_legend_swatches(image, box), box) for box in boxes]
        (entries, layout, confidence), legend_box = max(results, key=lambda value: len(value[0][0]))
        box_source = "autodetected"
    else:
        entries, layout, confidence = find_legend_swatches(image, legend_box)
        box_source = "explicit"
    pixels = np.asarray(image)
    border = np.concatenate((pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]))
    background = np.median(border, axis=0).round().astype(int)
    return {
        "source": str(image_path.resolve()),
        "image_size": list(image.size),
        "background_rgb": background.tolist(),
        "legend": {
            "box": list(legend_box),
            "box_source": box_source,
            "layout": layout,
            "confidence": round(confidence, 3),
            "entries": entries,
        },
    }


def _box(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(item) for item in value.split(","))
    if len(parts) != 4 or parts[2] <= parts[0] or parts[3] <= parts[1]:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return parts


def main() -> int:
    """Run the reference-spec extraction CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--legend-box", type=_box)
    args = parser.parse_args()
    spec = extract_spec(args.image, args.legend_box)
    Path(args.out).write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {args.out}: {len(spec['legend']['entries'])} legend entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
