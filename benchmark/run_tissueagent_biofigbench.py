"""Run TissueAgent against a single BioFigBench-Spatial figure-reproduction task.

BioFigBench ships one instance per figure panel:
  - ``tasks/<id>/task.json``  : the solver input — instruction, the panel's raw
                                dataset(s) with fetchable URLs, per-panel Methods
                                excerpts, the paper's code repo, and the caption.
  - ``tasks/<id>/panel.png``  : the gold panel (an INPUT here — the task is
                                "reproduce this panel", not "guess it blind").
  - ``references/<id>/``      : the oracle answer key. Never shown to the solver.

The solver must fetch the raw data itself, run the paper's workflow end-to-end, and
write ``output.png``. It is deliberately NOT given the per-figure source-data table.

This script builds the prompt from ``task.json``, stages ``panel.png`` + the paper
PDF as attachments, runs the TissueAgent CLI headlessly, and collects the result
into the prediction layout ``evaluation/evaluate.py`` expects:

  <run_dir>/predictions/<instance_id>/output.png

Usage:
  python benchmark/run_tissueagent_biofigbench.py 2023_NC_UnitedNet__fig_7_c \
      --run-dir benchmark/biofigbench-runs/run1
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH = REPO_ROOT / "benchmark" / "biofigbench-spatial"


def build_prompt(
    task: dict,
    out_png: Path,
    panel_ref: str,
    pdf_ref: str | None,
    include_code_sources: bool = False,
) -> str:
    """Assemble the solver prompt from the task record.

    Default is the **code-free** setting: the authors' repository is withheld and
    the solver must reconstruct the method from the paper's Methods text. Pass
    ``include_code_sources=True`` for the benchmark's as-shipped variant, where
    ``task.json``'s ``code_sources`` is handed over for the solver to reuse.
    """
    rd = task.get("raw_data") or {}
    datasets = "\n".join(
        f"  - {d.get('accession')} [{d.get('repository')}] {d.get('modality') or ''}\n"
        f"    url: {d.get('url')}\n"
        f"    {d.get('description') or ''}".rstrip()
        for d in (rd.get("datasets") or [])
    )
    methods = "\n".join(f"  - {m}" for m in (task.get("methods") or []))
    code_sources = "\n".join(f"  - {c}" for c in (task.get("code_sources") or []))
    avail = (rd.get("data_availability_text") or "").strip()

    parts = [
        task["instruction"],
        "",
        f'PAPER: "{task["paper_title"]}"',
        f"PANEL: Figure {task['figure_number']}, panel {task['panel_label']}",
        "",
        "PANEL CAPTION:",
        task.get("caption") or "",
        "",
        "FULL FIGURE CAPTION:",
        task.get("figure_caption") or "",
        "",
        "RAW DATASET(S) TO FETCH — download these yourself:",
        datasets or "  (none listed)",
    ]
    if avail:
        parts += ["", "DATA AVAILABILITY (from the paper):", avail[:2000]]
    parts += [
        "",
        "PAPER METHODS EXCERPTS FOR THIS PANEL:",
        methods or "  (none)",
    ]
    if include_code_sources:
        parts += [
            "",
            "CODE AVAILABILITY (the authors' repository — clone and reuse it):",
            code_sources or "  (none)",
        ]
    else:
        parts += [
            "",
            "IMPLEMENTATION CONSTRAINT — write the analysis code yourself:",
            "  Implement the method from the Methods description above and the paper.",
            "  Do not clone, download, install or copy the authors' own implementation",
            "  of this method, even if you can find it; the point of this task is to",
            "  reconstruct the analysis, not to re-run the authors' code. Standard,",
            "  general-purpose libraries (numpy, scanpy, pytorch, matplotlib, …) are",
            "  fine — a released package that implements this paper's method is not.",
        ]
    parts += [
        "",
        "FILES ALREADY STAGED FOR YOU:",
        f"  - {panel_ref} — the published panel you must reproduce (target image)",
    ]
    if pdf_ref:
        parts += [f"  - {pdf_ref} — the full paper PDF"]
    parts += [
        "",
        "HOW TO EXECUTE THIS:",
        "  Write ONE self-contained end-to-end script (data loading → preprocessing →",
        "  model → prediction → figure) and run it. Do not split the analysis across",
        "  many delegated sub-tasks: authoring code without ever executing it burns the",
        "  run. Get a rough end-to-end version producing a PNG at the required path",
        "  early, then iterate on fidelity — a crude panel beats no panel.",
        "",
        "REQUIRED OUTPUT:",
        f"  Save exactly one PNG of the reproduced panel to this absolute path:",
        f"    {out_png}",
        "  Recreate the panel's layout, subplot arrangement, colormap and annotations",
        "  as closely as the data allow. Do not copy, crop or re-encode the staged",
        "  target image — it is the reference to match, not the answer to hand back.",
        "",
        "You are NOT given the per-figure source-data table; regenerate it from the",
        "raw data as part of the workflow. You are scored primarily on how closely",
        "your output.png matches the published panel.",
    ]
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run TissueAgent on one BioFigBench panel")
    ap.add_argument("instance_id")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--model", default=None, help="model id passed to the CLI")
    ap.add_argument("--bench", type=Path, default=BENCH)
    ap.add_argument(
        "--include-code-sources",
        action="store_true",
        help="hand the authors' repo to the solver (benchmark's as-shipped variant); "
        "default is the code-free setting",
    )
    ap.add_argument(
        "--allow-dirty-library",
        action="store_true",
        help="start even if workspace/library holds a checked-out repo (contamination)",
    )
    args = ap.parse_args()

    # workspace/library/ survives across runs: a repo cloned by an earlier run is
    # readable by this one, which silently voids the code-free setting.
    if not args.include_code_sources and not args.allow_dirty_library:
        library = REPO_ROOT / "workspace" / "library"
        stale = [p.parent for p in library.rglob(".git")] if library.is_dir() else []
        if stale:
            raise SystemExit(
                "refusing to start a code-free run: the agent-visible library holds "
                "checked-out repo(s):\n"
                + "\n".join(f"  {p}" for p in stale)
                + "\nRemove them, or pass --allow-dirty-library to override."
            )

    task_file = args.bench / "tasks" / args.instance_id / "task.json"
    if not task_file.is_file():
        raise SystemExit(f"no such instance: {task_file}")
    task = json.loads(task_file.read_text())

    pred_dir = args.run_dir / "predictions" / args.instance_id
    pred_dir.mkdir(parents=True, exist_ok=True)
    out_png = (pred_dir / "output.png").resolve()

    panel = args.bench / task["panel_image"]
    pdf = args.bench / task["paper_pdf"] if task.get("paper_pdf") else None
    attach = [str(panel)]
    if pdf and pdf.is_file():
        attach.append(str(pdf))

    prompt = build_prompt(
        task,
        out_png,
        f"uploads/{panel.name}",
        f"uploads/{pdf.name}" if pdf and pdf.is_file() else None,
        include_code_sources=args.include_code_sources,
    )
    (args.run_dir / f"{args.instance_id}.prompt.txt").write_text(prompt)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "src" / "cli.py"),
        "--no-docker",
        "--json",
        "--task-id",
        args.instance_id,
        "--metrics-out",
        str(args.run_dir / f"{args.instance_id}.metrics.json"),
    ]
    if args.model:
        cmd += ["--model", args.model]
    for a in attach:
        cmd += ["--attach", a]
    cmd.append(prompt)

    print(f"[runner] instance={args.instance_id}", flush=True)
    print(f"[runner] output must land at {out_png}", flush=True)

    # Stream to disk rather than buffering: a figure-reproduction run is long, and
    # capture_output() hides the trace until it ends — including when it dies.
    out_path = args.run_dir / f"{args.instance_id}.stdout.txt"
    err_path = args.run_dir / f"{args.instance_id}.stderr.txt"
    with out_path.open("w") as fo, err_path.open("w") as fe:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=fo, stderr=fe, text=True)
    stdout_text = out_path.read_text(errors="ignore")

    result = {}
    for line in reversed(stdout_text.splitlines()):
        if line.startswith("{"):
            try:
                result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    (args.run_dir / f"{args.instance_id}.result.json").write_text(json.dumps(result, indent=2))

    # Fallback: the agent may have written the panel into the project outputs instead.
    if not out_png.is_file():
        from_workspace = _find_artifact_png(result)
        if from_workspace:
            shutil.copy2(from_workspace, out_png)
            print(f"[runner] recovered {from_workspace} -> {out_png}", flush=True)

    print(f"[runner] rc={proc.returncode} output_png={'YES' if out_png.is_file() else 'NO'}", flush=True)
    return 0 if out_png.is_file() else 1


def _find_artifact_png(result: dict) -> Path | None:
    """Pick the most likely panel PNG from the run's artifact list."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        from config import DATA_DIR
    except Exception:
        return None
    cands = [
        DATA_DIR / a
        for a in (result.get("artifacts") or [])
        if str(a).lower().endswith(".png")
    ]
    cands = [c for c in cands if c.is_file()]
    if not cands:
        return None
    named = [c for c in cands if c.name == "output.png"]
    return named[0] if named else max(cands, key=lambda p: p.stat().st_mtime)


if __name__ == "__main__":
    raise SystemExit(main())
