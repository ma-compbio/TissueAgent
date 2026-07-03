#!/usr/bin/env python3
"""compare_figures.py -- fidelity self-evaluation for the 'figure-reproduce' skill.

WHAT IT DOES
    Compares a reproduced figure against the target (original) figure and returns a
    similarity verdict. This is the numeric feedback that drives the agent's
    reflect-and-retry loop: if the reproduction is far from the target, the agent
    should inspect *why* and try again.

    Metrics computed (each degrades gracefully if an optional dep is missing):
      * pHash Hamming distance  -- perceptual hash difference (0 = identical layout).
      * SSIM                     -- structural similarity on 512x512 grayscale (0..1).
      * ORB good-match count     -- number of robust keypoint matches (higher = better).
      * B-level prior            -- a coarse B1..B5 bucket derived from SSIM.

    IMPORTANT: the B-level prior is ONLY a numeric hint. The agent's own visual
    judgment against the B1..B5 rubric is authoritative -- a plot can be a perfect
    scientific reproduction yet score low SSIM (different colormap, jitter, axis
    ticks), or look similar yet be scientifically wrong.

USAGE
    python compare_figures.py <original_image> <reproduced_image> [--out compare_diff.png] [--json]

    --out   Where to write the side-by-side (original | reproduced) PNG.
            Default: ./compare_diff.png
    --json  Emit all metrics as machine-readable JSON instead of prose.

PORTABILITY
    Part of the 'figure-reproduce' skill: a single self-contained file with NO
    dependency on any project package. It runs anywhere Pillow + numpy are present.
    scikit-image (SSIM), opencv (ORB), and imagehash (pHash) are optional enhancers;
    when absent the script uses built-in numpy fallbacks or skips that metric with a
    one-line install hint.
"""

from __future__ import annotations

import argparse
import json
import sys

# --- Mandatory deps: Pillow + numpy. Everything else is optional. -----------------
try:
    import numpy as np
    from PIL import Image
except ImportError as exc:  # pragma: no cover - hard requirement
    sys.stderr.write(
        f"FATAL: this script needs numpy and Pillow ({exc}). "
        "Install with: pip install numpy Pillow\n"
    )
    sys.exit(2)


# ---------------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------------
def load_rgb(path: str) -> Image.Image:
    """Open an image as RGB, or exit non-zero on a real usage error (bad path)."""
    try:
        return Image.open(path).convert("RGB")
    except (FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"ERROR: cannot read image '{path}': {exc}\n")
        sys.exit(2)


def to_gray_array(img: Image.Image, size: int = 512) -> np.ndarray:
    """Grayscale, resized to size x size, as float64 in [0, 255]."""
    gray = img.convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(gray, dtype=np.float64)


# ---------------------------------------------------------------------------------
# pHash: prefer imagehash, else a compact 8x8 DCT perceptual hash
# ---------------------------------------------------------------------------------
def _dct_1d(matrix: np.ndarray) -> np.ndarray:
    """Type-II DCT applied along the last axis (no scipy needed)."""
    n = matrix.shape[-1]
    k = np.arange(n)
    # basis[u, x] = cos(pi/N * (x + 0.5) * u)
    basis = np.cos(np.pi / n * (k[:, None] + 0.5) * k[None, :])
    return matrix @ basis.T


def phash_bits(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> np.ndarray:
    """Compact DCT-based 64-bit perceptual hash returned as a boolean array."""
    img_size = hash_size * highfreq_factor
    pixels = np.asarray(
        img.convert("L").resize((img_size, img_size), Image.BILINEAR),
        dtype=np.float64,
    )
    # 2D DCT = 1D DCT on rows then on columns.
    dct = _dct_1d(_dct_1d(pixels).T).T
    low = dct[:hash_size, :hash_size]  # keep the low-frequency top-left block
    med = np.median(low[1:, 1:])  # exclude the DC term (low[0,0]) from the median
    return (low > med).flatten()


def phash_hamming(orig: Image.Image, repro: Image.Image) -> tuple[int, str]:
    """Return (hamming_distance, path_label). Prefers the imagehash library."""
    try:
        import imagehash

        h1 = imagehash.phash(orig)
        h2 = imagehash.phash(repro)
        return int(h1 - h2), "imagehash"
    except ImportError:
        b1 = phash_bits(orig)
        b2 = phash_bits(repro)
        return int(np.count_nonzero(b1 != b2)), "numpy-dct-fallback"


# ---------------------------------------------------------------------------------
# SSIM: prefer skimage, else a windowed numpy fallback
# ---------------------------------------------------------------------------------
def _ssim_numpy(a: np.ndarray, b: np.ndarray, win: int = 7) -> float:
    """Windowed mean/variance/covariance SSIM (Wang et al. 2004) in pure numpy.

    Uses a uniform (box) sliding window of size `win`; constants match the standard
    SSIM formulation for an 8-bit dynamic range (L=255).
    """
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    # Sliding local statistics via a box filter implemented with cumulative sums.
    def box_mean(x: np.ndarray) -> np.ndarray:
        pad = win // 2
        xp = np.pad(x, pad, mode="reflect")
        # integral image for O(1) window sums
        cs = np.cumsum(np.cumsum(xp, axis=0), axis=1)
        cs = np.pad(cs, ((1, 0), (1, 0)), mode="constant")
        h, w = x.shape
        s = (
            cs[win:win + h, win:win + w]
            - cs[0:h, win:win + w]
            - cs[win:win + h, 0:w]
            + cs[0:h, 0:w]
        )
        return s / (win * win)

    mu_a = box_mean(a)
    mu_b = box_mean(b)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    var_a = box_mean(a * a) - mu_a2
    var_b = box_mean(b * b) - mu_b2
    cov_ab = box_mean(a * b) - mu_ab

    ssim_map = ((2 * mu_ab + c1) * (2 * cov_ab + c2)) / (
        (mu_a2 + mu_b2 + c1) * (var_a + var_b + c2)
    )
    return float(np.clip(ssim_map.mean(), -1.0, 1.0))


def compute_ssim(orig: Image.Image, repro: Image.Image) -> tuple[float, str]:
    """Return (ssim, path_label) on 512x512 grayscale. Prefers scikit-image."""
    a = to_gray_array(orig)
    b = to_gray_array(repro)
    try:
        from skimage.metrics import structural_similarity as sk_ssim

        val = sk_ssim(a, b, data_range=255.0)
        return float(val), "skimage"
    except ImportError:
        return _ssim_numpy(a, b), "numpy-fallback"


# ---------------------------------------------------------------------------------
# ORB good-match count (opencv only; skipped if cv2 is absent)
# ---------------------------------------------------------------------------------
def orb_good_matches(orig: Image.Image, repro: Image.Image) -> tuple[int | None, str]:
    """Return (good_match_count, note). None when opencv is not installed."""
    try:
        import cv2
    except ImportError:
        return None, "skipped: opencv not installed (pip install opencv-python-headless)"

    a = np.asarray(orig.convert("L"))
    b = np.asarray(repro.convert("L"))
    orb = cv2.ORB_create(nfeatures=500)
    _, des_a = orb.detectAndCompute(a, None)
    _, des_b = orb.detectAndCompute(b, None)
    if des_a is None or des_b is None:
        return 0, "computed: no descriptors in one image"

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des_a, des_b)
    good = sum(1 for m in matches if m.distance < 64)
    return good, "computed"


# ---------------------------------------------------------------------------------
# B-level prior from the SSIM ladder
# ---------------------------------------------------------------------------------
def b_level_from_ssim(ssim: float) -> str:
    if ssim >= 0.95:
        return "B5"
    if ssim >= 0.85:
        return "B4"
    if ssim >= 0.70:
        return "B3"
    if ssim >= 0.40:
        return "B2"
    return "B1"


# ---------------------------------------------------------------------------------
# Side-by-side comparison image
# ---------------------------------------------------------------------------------
def write_side_by_side(orig: Image.Image, repro: Image.Image, out_path: str) -> None:
    """Write 'original | reproduced' scaled to a common height, with a gap."""
    target_h = max(orig.height, repro.height)

    def scale_to_h(img: Image.Image) -> Image.Image:
        w = max(1, round(img.width * target_h / img.height))
        return img.resize((w, target_h), Image.BILINEAR)

    left = scale_to_h(orig)
    right = scale_to_h(repro)
    gap = 10
    canvas = Image.new("RGB", (left.width + gap + right.width, target_h), "white")
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))
    canvas.save(out_path)


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a reproduced figure against the target and report similarity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("original", help="path to the original / target figure")
    parser.add_argument("reproduced", help="path to the reproduced figure")
    parser.add_argument("--out", default="./compare_diff.png", help="side-by-side PNG output path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    orig = load_rgb(args.original)
    repro = load_rgb(args.reproduced)

    ham, phash_path = phash_hamming(orig, repro)
    ssim, ssim_path = compute_ssim(orig, repro)
    orb_count, orb_note = orb_good_matches(orig, repro)
    b_prior = b_level_from_ssim(ssim)

    write_side_by_side(orig, repro, args.out)

    which = {
        "phash": phash_path,
        "ssim": ssim_path,
        "orb": "cv2" if orb_count is not None else "unavailable",
    }

    if args.json:
        payload = {
            "original": args.original,
            "reproduced": args.reproduced,
            "phash_hamming": ham,
            "ssim": round(ssim, 4),
            "orb_good_matches": orb_count,
            "b_level_prior": b_prior,
            "b_level_prior_note": (
                "SSIM-derived numeric prior ONLY -- it ignores color/palette and label "
                "correctness, so a wrong-colormap or wrong-label plot can still score high "
                "here. The agent's visual B1-B5 judgment is authoritative."
            ),
            "which_metrics_computed": which,
            "diff_image": args.out,
        }
        print(json.dumps(payload, indent=2))
    else:
        orb_str = str(orb_count) if orb_count is not None else f"(n/a - {orb_note})"
        print("Figure comparison (fidelity self-evaluation)")
        print(f"  original    : {args.original}")
        print(f"  reproduced  : {args.reproduced}")
        print("  ---")
        print(f"  pHash Hamming distance : {ham:>4}   [{phash_path}]  (0 = identical, lower better)")
        print(f"  SSIM (512x512 gray)    : {ssim:.4f} [{ssim_path}]  (1.0 = identical)")
        print(f"  ORB good matches       : {orb_str:>4}   [{which['orb']}]  (higher better)")
        print("  ---")
        print(f"  B-level PRIOR          : {b_prior}  (from SSIM ladder)")
        print("  NOTE: this B-level is only a numeric prior; it ignores color/palette and")
        print("        label correctness (a wrong-colormap plot can still score high). Your")
        print("        visual B1-B5 judgment is authoritative -- confirm or override by eye.")
        print(f"  side-by-side diff      : {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
