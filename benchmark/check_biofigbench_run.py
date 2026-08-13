"""Audit a BioFigBench run for the two ways a solver can cheat.

1. **Author code** — the code-free setting withholds the paper's repository and
   forbids using it, but the constraint is prompt-level only: the paper PDF still
   names the repo. This scans the run transcript and everything the agent wrote for
   clone/install/import of the authors' implementation.

2. **Copied panel** — the gold panel is staged as an input, so ``output.png`` could
   be a re-encode of the target rather than a reproduction. This compares them
   byte-wise, pixel-wise, and by perceptual hash (a genuine reproduction differs
   substantially; near-zero distance is suspicious).

Usage:
  python benchmark/check_biofigbench_run.py <run_dir> <instance_id> [--project-dir DIR]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH = REPO_ROOT / "benchmark" / "biofigbench-spatial"

# Signals that the solver reached for the authors' own implementation.
AUTHOR_CODE_PATTERNS = [
    r"github\.com/[\w.-]+/[\w.-]*unitednet",
    r"LiuLab-Bioelectronics",
    r"git\s+clone\s+\S*unitednet",
    r"pip\s+install\s+\S*unitednet",
    r"from\s+src\.(interface|configs|modules)\s+import",
    r"import\s+unitednet",
]
# Generic "fetched someone's repo" signals — reported separately, may be legitimate.
REPO_FETCH_PATTERNS = [r"git\s+clone\s+\S+", r"pip\s+install\s+git\+\S+"]


def scan_text(text: str, patterns: list[str]) -> list[tuple[str, str]]:
    """Return (pattern, matched line) for every pattern hit, deduped."""
    hits, seen = [], set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            line = text[max(0, m.start() - 100) : m.end() + 100].replace("\n", " ⏎ ")
            key = (pat, line[:120])
            if key not in seen:
                seen.add(key)
                hits.append((pat, line.strip()))
    return hits


def scan_workspace_library(library: Path) -> list[dict]:
    """Author code sitting in the agent-visible library, whoever put it there.

    ``workspace/library/`` survives across runs, so a repo cloned by an earlier
    run is readable by a later "code-free" one. Report every checkout found with
    its remote and mtime, so a clone can be attributed to a run window.
    """
    import subprocess

    found = []
    if not library.is_dir():
        return found
    for git_dir in library.rglob(".git"):
        repo = git_dir.parent
        remote = ""
        try:
            remote = subprocess.run(
                ["git", "-C", str(repo), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except Exception:
            pass
        found.append(
            {
                "path": str(repo),
                "remote": remote,
                "mtime": __import__("datetime").datetime.fromtimestamp(
                    repo.stat().st_mtime
                ).isoformat(timespec="seconds"),
            }
        )
    # Non-git drops (zip downloads, copied trees) are worth naming too.
    for child in library.glob("files/*"):
        if child.is_dir() and not (child / ".git").exists():
            found.append(
                {
                    "path": str(child),
                    "remote": "(no git metadata)",
                    "mtime": __import__("datetime").datetime.fromtimestamp(
                        child.stat().st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )
    return found


def gather_sources(run_dir: Path, instance_id: str, project_dir: Path | None) -> list[Path]:
    """Transcript files plus everything the agent wrote during the run."""
    files = [
        p
        for p in [
            run_dir / f"{instance_id}.stdout.txt",
            run_dir / f"{instance_id}.stderr.txt",
            run_dir / f"{instance_id}.result.json",
            run_dir / f"{instance_id}.metrics.json",
            run_dir / "runner.log",
        ]
        if p.is_file()
    ]
    if project_dir and project_dir.is_dir():
        files += [
            p
            for p in project_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".py", ".ipynb", ".sh", ".json", ".md", ".txt", ".log"}
        ]
    return files


def compare_images(gold: Path, cand: Path) -> dict:
    """Byte / pixel / perceptual comparison of the candidate against the gold panel."""
    out: dict = {}
    gb, cb = gold.read_bytes(), cand.read_bytes()
    out["identical_bytes"] = gb == cb
    out["gold_sha256"] = hashlib.sha256(gb).hexdigest()[:16]
    out["cand_sha256"] = hashlib.sha256(cb).hexdigest()[:16]
    try:
        import imagehash
        import numpy as np
        from PIL import Image

        gi, ci = Image.open(gold).convert("RGB"), Image.open(cand).convert("RGB")
        out["gold_size"] = gi.size
        out["cand_size"] = ci.size
        out["phash_hamming"] = int(imagehash.phash(gi) - imagehash.phash(ci))
        if gi.size == ci.size:
            out["identical_pixels"] = bool(np.array_equal(np.asarray(gi), np.asarray(ci)))
        else:
            out["identical_pixels"] = False
    except ImportError as e:
        out["image_metrics_error"] = f"{e} (pip install pillow imagehash numpy)"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a BioFigBench run for cheating")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("instance_id")
    ap.add_argument("--project-dir", type=Path, default=None, help="agent workspace project dir")
    ap.add_argument(
        "--library",
        type=Path,
        default=REPO_ROOT / "workspace" / "library",
        help="agent-visible library dir; persists across runs, so audit it too",
    )
    ap.add_argument(
        "--assert-clean",
        action="store_true",
        help="pre-run check: exit non-zero if the library holds any checked-out repo, "
        "then stop (no run artifacts needed)",
    )
    args = ap.parse_args()

    if args.assert_clean:
        stale = scan_workspace_library(args.library)
        for s in stale:
            print(f"  ! {s['path']}  remote={s['remote']}  mtime={s['mtime']}")
        print(f"library checkouts: {len(stale)} — {'DIRTY' if stale else 'clean'}")
        return 1 if stale else 0

    report: dict = {"instance_id": args.instance_id, "run_dir": str(args.run_dir)}

    sources = gather_sources(args.run_dir, args.instance_id, args.project_dir)
    report["files_scanned"] = len(sources)
    author_hits, repo_hits = [], []
    for f in sources:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for pat, line in scan_text(text, AUTHOR_CODE_PATTERNS):
            author_hits.append({"file": str(f), "pattern": pat, "context": line[:300]})
        for pat, line in scan_text(text, REPO_FETCH_PATTERNS):
            repo_hits.append({"file": str(f), "pattern": pat, "context": line[:300]})
    report["author_code_hits"] = author_hits
    report["repo_fetch_hits"] = repo_hits
    report["library_checkouts"] = scan_workspace_library(args.library)

    task = json.loads((BENCH / "tasks" / args.instance_id / "task.json").read_text())
    gold = BENCH / task["panel_image"]
    cand = args.run_dir / "predictions" / args.instance_id / "output.png"
    report["output_png_exists"] = cand.is_file()
    if cand.is_file():
        report["image_comparison"] = compare_images(gold, cand)

    out_file = args.run_dir / f"{args.instance_id}.audit.json"
    out_file.write_text(json.dumps(report, indent=2))

    print(f"files scanned         : {report['files_scanned']}")
    print(f"author-code hits      : {len(author_hits)}")
    for h in author_hits[:10]:
        print(f"  ! {h['pattern']}  in {Path(h['file']).name}")
        print(f"      …{h['context'][:200]}")
    print(f"other repo fetches    : {len(repo_hits)}")
    for h in repo_hits[:10]:
        print(f"  - {h['context'][:160]}")
    libs = report["library_checkouts"]
    print(f"library checkouts     : {len(libs)}  (readable by the agent, survive across runs)")
    for lib in libs[:10]:
        print(f"  ! {Path(lib['path']).name}  remote={lib['remote'] or '(none)'}  mtime={lib['mtime']}")
    ic = report.get("image_comparison")
    if ic:
        print(
            f"output vs gold        : identical_bytes={ic.get('identical_bytes')} "
            f"identical_pixels={ic.get('identical_pixels')} phash={ic.get('phash_hamming')}"
        )
    elif not report["output_png_exists"]:
        print("output vs gold        : no output.png produced")
    print(f"\nwrote {out_file}")
    return 1 if author_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
