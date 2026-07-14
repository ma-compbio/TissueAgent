#!/usr/bin/env python3
"""Download Spotiphy Zenodo Xenium_FAD_1.h5ad into the benchmark fixture."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

URL = "https://zenodo.org/api/records/10520022/files/Xenium_FAD_1.h5ad/content"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2025_NM_Spotiphy/dataset.h5ad"),
    )
    p.add_argument(
        "--download-dir",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2025_NM_Spotiphy/_download"),
    )
    args = p.parse_args()
    args.download_dir.mkdir(parents=True, exist_ok=True)
    raw = args.download_dir / "Xenium_FAD_1.h5ad"
    if not raw.is_file() or raw.stat().st_size < 1_000_000:
        print(f"Downloading {URL} ...")
        urllib.request.urlretrieve(URL, raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.resolve() != raw.resolve():
        if args.out.exists() or args.out.is_symlink():
            args.out.unlink()
        args.out.symlink_to(raw.resolve())

    import anndata as ad

    a = ad.read_h5ad(args.out, backed="r")
    n_obs, n_vars = a.n_obs, a.n_vars
    print(f"Ready {args.out} shape=({n_obs}, {n_vars})")

    manifest_path = args.out.parent / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        rel = str(args.out.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        rel = str(args.out)
    manifest.update(
        {
            "status": "ready",
            "h5ad_path": rel,
            "n_obs": int(n_obs),
            "n_vars": int(n_vars),
            "source": "zenodo:10.5281/zenodo.10520022",
            "sample_id": "Xenium_FAD_1",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
