"""Generate the expert reference ensembles (run once per dataset, no agent).

Runs the six shipped CCC skill scripts — the same frozen scripts the agent's
skills invoke — directly as subprocesses against the staged benchmark inputs.
The resulting ``ccc_ensemble.csv`` per dataset is the accuracy oracle: an
agent run that executes the pipeline correctly converges to it exactly.

Usage::

    python benchmark/optimizer_ccc/make_reference.py [--datasets merfish ...] [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datasets import (  # noqa: E402
    DATASETS,
    PREP_ARGS,
    REFERENCE_DIR,
    REPO_ROOT,
    staged_path,
)

SKILLS = REPO_ROOT / "knowledge" / "skills"
PIPELINE = [
    SKILLS / "ccc-data-prep" / "scripts" / "ccc_data_prep.py",
    SKILLS / "ccc-liana" / "scripts" / "ccc_liana.py",
    SKILLS / "ccc-commot" / "scripts" / "ccc_commot.py",
    SKILLS / "ccc-stlearn" / "scripts" / "ccc_stlearn.py",
    SKILLS / "ccc-decoupler" / "scripts" / "ccc_decoupler.py",
    SKILLS / "ccc-aggregate" / "scripts" / "ccc_aggregate.py",
]
# Files archived next to the reference ensemble for drift debugging.
KEEP = ["ccc_ensemble.csv", "ccc_lr_common.csv", "logs/ccc_data_prep.json"]


def make_reference(name: str, *, keep_work: bool = False) -> Path:
    d = DATASETS[name]
    input_h5ad = staged_path(name)
    if not input_h5ad.is_file():
        raise SystemExit(f"{name}: staged input {input_h5ad} missing — run prepare_inputs.py first")

    ref_dir = REFERENCE_DIR / name
    work = ref_dir / "work"
    if work.exists():
        shutil.rmtree(work)
    (work / "project" / "outputs").mkdir(parents=True)

    prep_cmd = [
        sys.executable, str(PIPELINE[0]),
        "--adata", str(input_h5ad),
        "--cell-type", d["cell_type"],
        "--species", d["species"],
        "--crop-n", str(PREP_ARGS["crop_n"]),
        "--max-pairs", str(PREP_ARGS["max_pairs"]),
        "--knn-k", str(PREP_ARGS["knn_k"]),
    ]
    commands = [prep_cmd] + [[sys.executable, str(s)] for s in PIPELINE[1:]]

    for cmd in commands:
        script = Path(cmd[1]).name
        print(f"[{name}] running {script} …", flush=True)
        log = ref_dir / f"{script}.log"
        with log.open("w") as fh:
            proc = subprocess.run(cmd, cwd=work, stdout=fh, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise SystemExit(f"{name}: {script} failed (exit {proc.returncode}); see {log}")

    for rel in KEEP:
        src = work / "project" / "outputs" / rel
        if not src.is_file():
            raise SystemExit(f"{name}: pipeline finished but {rel} is missing")
        dst = ref_dir / Path(rel).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    if not keep_work:
        shutil.rmtree(work)
    return ref_dir / "ccc_ensemble.csv"


def _git_hash(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "hash-object", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS), choices=list(DATASETS))
    ap.add_argument("--force", action="store_true", help="Rebuild an existing reference.")
    ap.add_argument("--keep-work", action="store_true", help="Keep the work/ dir for debugging.")
    args = ap.parse_args(argv)

    manifest_path = REFERENCE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    for name in args.datasets:
        ref_csv = REFERENCE_DIR / name / "ccc_ensemble.csv"
        if ref_csv.is_file() and not args.force:
            print(f"[skip] {name}: reference exists (use --force to rebuild)")
            continue
        csv = make_reference(name, keep_work=args.keep_work)
        manifest[name] = {
            "input": staged_path(name).name,
            "cell_type": DATASETS[name]["cell_type"],
            "species": DATASETS[name]["species"],
            "prep_args": PREP_ARGS,
            "script_hashes": {p.name: _git_hash(p) for p in PIPELINE},
        }
        print(f"[done] {name}: {csv}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
