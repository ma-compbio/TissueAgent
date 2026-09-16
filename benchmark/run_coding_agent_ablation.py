"""Compare the two coding-agent implementations on Lohoff Fig 2b, WITHOUT a colormap.

Two arms, identical task, identical model, identical scorer:

  * ``stock``     -- ``agents.agent_registry.coding_agent_cache`` (Jupyter
                     kernel, python()/r(), recruiter-injected skills, failure budgets).
  * ``deepagent`` -- ``agents.agent_registry.coding_agent`` (stateless
                     shell ``execute``, model-selected skills, no budgets).

The arm is chosen by ``TISSUEAGENT_CODING_AGENT``, which the agent registry reads
at import time, so this script must be launched once per arm with the env var
already set. Running both arms in one process would silently give the second arm
the first arm's constructor.

Task shape mirrors ``demo/figure_recreation_lohoff-2b.ipynb`` with one deliberate
change: ``colormap.yaml`` is NOT staged and the prompt does not mention it, so the
palette must be recovered from the reference image. That is the discriminating
part of the task -- with a colormap supplied, both arms just read the file.

Usage (one arm per invocation):
    python benchmark/run_coding_agent_ablation.py \
        --arm deepagent --out benchmark/biofigbench/coding_agent_ablation
    TISSUEAGENT_CODING_AGENT=cache python benchmark/run_coding_agent_ablation.py \
        --arm stock --out benchmark/biofigbench/coding_agent_ablation
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from queue import Queue

REPO_ROOT = Path(__file__).resolve().parent.parent
# ``knowledge`` is a top-level package at the repo root, alongside (not inside)
# ``src`` -- config imports it, so the root must be on the path too.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "demo"))

TASK = "figure_recreation_lohoff-2b_nocolormap"

# The reference panel and dataset the demo notebook uses. colormap.yaml is
# deliberately absent -- see the module docstring.
DEMO_DATA = REPO_ROOT / "demo" / "data"
DATASET = "dataset_lohoff_et_al_seqfish.h5ad"
REFERENCE = "reference_lohoff-2b.png"

# Identical to the notebook prompt minus the ", according to colormap.yaml"
# clause. Everything else -- inverted y-axis, the reference image, the
# "as close as possible" instruction -- is preserved verbatim so the only
# variable between this and the demo is the palette source.
PROMPT = """
I have provided a spatial transcriptomics dataset in dataset_lohoff_et_al_seqfish.h5ad. Help me plot a spatial
scatterplot, where the position of each cell is its location, and the color of a cell is determined by the cell
type. The y-axis should be inverted. A reference image is included reference_lohoff-2b.png.
The plot should be as close as possible to the reference.
""".replace("\n", " ").strip()


def stage_inputs() -> None:
    """Reset the workspace and stage dataset + reference (no colormap)."""
    from config import DATA_DIR, DATASET_DIR, UPLOADS_DIR
    from notebook_utils import _reset_data_directories

    _reset_data_directories()
    # _reset_data_directories only clears SUBDIRECTORIES; loose files left at the
    # workspace root by earlier runs survive it. That matters here: a previous run
    # left a validation_tmp.txt naming a "celltype_colorkey.tsv", i.e. exactly the
    # palette artifact this no-colormap condition is meant to withhold.
    for stray in DATA_DIR.glob("*"):
        # Never delete this run's own lock -- doing so silently disarms the
        # concurrency guard for whatever starts next.
        if stray.is_file() and stray.name not in ("kernel_gateway.log", ".ablation_run.lock"):
            stray.unlink()
            print(f"  removed stray workspace file: {stray.name}")

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    # These are tracked in git (they keep the empty input dirs alive); the reset
    # above removes them, so put them back rather than leaving a dirty worktree.
    (DATASET_DIR / ".gitkeep").touch()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / ".gitkeep").touch()
    shutil.copy(DEMO_DATA / DATASET, DATASET_DIR / DATASET)
    shutil.copy(DEMO_DATA / REFERENCE, UPLOADS_DIR / REFERENCE)
    # The stock coding agent is a CustomAgent and never calls
    # sync_workspace_skills (only node_factories' ReAct path does), so without
    # this its prompt cites `project/skills/figure-reproduce/scripts/...` while
    # nothing exists on disk -- the agent cannot run the skill's tooling even if
    # it tries. The deepagent arm materializes per-invocation on its own; doing
    # it here too just means both arms start from the same populated tree.
    try:
        from agents.skills_workspace import sync_workspace_skills

        print("Materialized skills:", sync_workspace_skills(["figure-reproduce"]))
    except Exception as e:
        print(f"WARNING: skill materialization failed: {e}")

    staged = sorted(str(f.relative_to(DATA_DIR)) for f in DATA_DIR.rglob("*") if f.is_file())
    print("Staged inputs:")
    for f in staged:
        print(f"  - {f}")
    # Only the agent-visible INPUT dirs may not carry a colormap. The registry's
    # own materialized skill assets legitimately include build_colormap.py, so
    # scanning all of DATA_DIR here would false-positive on the skill tooling.
    inputs = [p.name for p in list(DATASET_DIR.rglob("*")) + list(UPLOADS_DIR.rglob("*")) if p.is_file()]
    assert not any("colormap" in n for n in inputs), f"colormap must NOT be staged: {inputs}"


def build_graph(arm: str):
    """Compile the TissueAgent graph for *arm*.

    The stock arm needs a live ``KernelClient`` (Jupyter Kernel Gateway); the
    deepagent arm ignores it but ``graph.py`` filters ctor kwargs by signature,
    so passing it unconditionally is safe.
    """
    from openai import RateLimitError

    from agents.agent_registry.coding_agent_cache.sandbox import KernelClient
    from graph.graph import create_tissueagent_graph

    def _bind_retry(model):
        return model.with_retry(
            retry_if_exception_type=(RateLimitError,),
            stop_after_attempt=6,
        )

    from config import DATA_DIR

    state_queue: Queue = Queue()
    kernel_client = KernelClient()
    # Only the web server calls set_workspace(); a direct caller must do it too.
    # Left unset, ``_workspace`` is None, ``_seed_kernel`` returns early, and every
    # relative path the agent writes resolves against the *gateway's launch cwd*
    # instead of the workspace -- which is how `library/...` became
    # `workspace/workspace/library/...` and every read failed.
    kernel_client.set_workspace(DATA_DIR.resolve(), force_restart=True)
    graph = create_tissueagent_graph(
        state_queue, _bind_retry, kernel_client=kernel_client
    )
    return graph.compile(), state_queue


def collect_artifacts(out_dir: Path) -> None:
    """Copy everything the run produced (minus the staged inputs) into *out_dir*."""
    from config import DATA_DIR

    out_dir.mkdir(parents=True, exist_ok=True)
    # "library" holds the staged INPUTS (a 31MB .h5ad + the reference PNG). Copying
    # it per arm doubles the run's disk footprint for no evidentiary value -- the
    # inputs are identical across arms and live in demo/data/. The reference PNG is
    # small and worth keeping, so only the dataset is skipped, below.
    exclude = {"dataset", "uploads"}
    for sub in DATA_DIR.iterdir():
        if sub.is_dir() and sub.name not in exclude:
            dst = out_dir / sub.name
            shutil.copytree(
                sub, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("*.h5ad"),
            )
            # Copied skill assets keep their read-only mode; restore owner-write
            # so a later re-run can clean this directory up.
            for p in dst.rglob("*"):
                try:
                    p.chmod(p.stat().st_mode | 0o200)
                except OSError:
                    pass
            print(f"Collected {sub.name}/")


def find_output_figure(out_dir: Path) -> Path | None:
    """Locate the reproduced panel among the collected artifacts.

    Prefer the notebook's conventional name, then any PNG under a ``figures``
    directory, then the largest PNG anywhere -- the arms are free to name their
    output, and a missing figure is a real result we must record, not crash on.
    """
    exact = out_dir / "figures" / "spatial_scatter.png"
    if exact.is_file():
        return exact
    candidates = [p for p in out_dir.rglob("figures/*.png")]
    if not candidates:
        candidates = [p for p in out_dir.rglob("*.png")]

    def is_output(p: Path) -> bool:
        # Underscore-prefixed names are the agents' own scratch (quick looks,
        # marker-size sweeps like _trial_s4.png). Scoring one of those instead of
        # the finished panel understates the arm badly.
        if p.name.startswith("_") or "_trace" in p.parts:
            return False
        # Never score the run's own INPUTS or the scorer's own artifacts. The
        # staged reference is copied into library/files, and picking it up would
        # silently "score" the target against itself -- SSIM 1.0 for a run that
        # produced nothing. Same for any comparison PNG a skill wrote.
        parts = set(p.parts)
        if "library" in parts or "uploads" in parts or "skills" in parts:
            return False
        name = p.name.lower()
        return not any(k in name for k in ("compare", "diff", "score_", "sidebyside", "reference"))

    candidates = [p for p in candidates if is_output(p)]
    if not candidates:
        return None
    # An arm that runs a repair loop writes attempt1..attemptN and ACCEPTS the
    # last one (its repro note says so). Size is a poor proxy there -- an earlier,
    # denser attempt can be the largest file -- so prefer the highest attempt
    # number when that naming is present.
    import re as _re

    attempts = [(int(m.group(1)), p) for p in candidates
                if (m := _re.search(r"attempt(\d+)", p.name))]
    if attempts:
        return max(attempts)[1]
    return max(candidates, key=lambda p: p.stat().st_size)


def score(figure: Path, out_dir: Path) -> dict:
    """Run the shared scorer (figure-reproduce/compare_figures.py) on *figure*."""
    scorer = REPO_ROOT / "knowledge" / "skills" / "figure-reproduce" / "scripts" / "compare_figures.py"
    reference = DEMO_DATA / REFERENCE
    cmd = [
        sys.executable, str(scorer), str(reference), str(figure),
        "--json", "--out", str(out_dir / "score_sidebyside.png"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:], "returncode": proc.returncode}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "scorer produced non-JSON output", "stdout": proc.stdout[-2000:]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", required=True, choices=["stock", "deepagent"])
    ap.add_argument("--out", default="benchmark/biofigbench/coding_agent_ablation")
    ap.add_argument("--model", default="gpt-5.4")
    args = ap.parse_args()

    # Guard the import-time coupling described in the module docstring.
    from agents.coding_agent_selection import coding_agent_implementation

    want = "deepagent" if args.arm == "deepagent" else "cache"
    got = coding_agent_implementation()
    if want != got:
        print(
            f"FATAL: --arm={args.arm} selects {want!r}, but "
            f"TISSUEAGENT_CODING_AGENT selects {got!r}. Relaunch with the matching setting.",
            file=sys.stderr,
        )
        return 2

    # Both arms share one workspace (DATA_DIR) and stage_inputs() wipes it, so two
    # concurrent runs corrupt each other -- the second reset deletes the first's
    # in-flight outputs, and whichever finishes last collects a mixture. Refuse to
    # start rather than silently produce an uninterpretable result.
    lock = REPO_ROOT / "workspace" / ".ablation_run.lock"
    if lock.exists():
        owner = lock.read_text().strip()
        print(f"FATAL: another ablation run is active ({owner}). "
              f"Wait for it, or remove {lock} if it is stale.", file=sys.stderr)
        return 3
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"arm={args.arm} pid={os.getpid()}")

    out_dir = REPO_ROOT / args.out / args.arm
    if out_dir.exists():
        # sync_workspace_skills materializes skill assets read-only, and rmtree
        # cannot unlink a file inside a dir it lacks write permission on. Restore
        # owner-write across the tree before removing a previous run's output.
        for p in out_dir.rglob("*"):
            try:
                p.chmod(p.stat().st_mode | 0o200)
            except OSError:
                pass
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    import logging

    from notebook_utils import tee_output

    log_path = out_dir / "transcript.log"
    log_path.write_text("")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    from models import set_selection

    # gpt-5.4 rejects reasoning_effort outright when function tools are bound on
    # /v1/chat/completions, and every agent here binds tools. "none" omits the
    # parameter (see models.build_chat_model). Verified live before this run.
    os.environ.setdefault("TISSUEAGENT_REASONING_EFFORT", "none")
    set_selection(orchestration=args.model, worker=args.model)

    record: dict = {
        "arm": args.arm,
        "task": TASK,
        "model": args.model,
        "reasoning_effort": os.environ.get("TISSUEAGENT_REASONING_EFFORT"),
        "colormap_supplied": False,
        "prompt": PROMPT,
    }

    t0 = time.time()
    with tee_output(log_path):
        try:
            stage_inputs()
            agent, _q = build_graph(args.arm)
            result = agent.invoke({"messages": [("user", PROMPT)]})
            record["final_message"] = str(result["messages"][-1].content)
            record["status"] = "completed"
        except Exception as e:
            record["status"] = "error"
            record["error"] = f"{type(e).__name__}: {e}"
            record["traceback"] = traceback.format_exc()
            print(record["traceback"])
    record["wall_seconds"] = round(time.time() - t0, 1)

    try:
        collect_artifacts(out_dir)
    except Exception as e:
        record["collect_error"] = str(e)

    figure = find_output_figure(out_dir)
    record["output_figure"] = str(figure.relative_to(out_dir)) if figure else None
    if figure is not None:
        record["score"] = score(figure, out_dir)
    else:
        record["score"] = {"error": "no output figure produced"}

    (out_dir / "run_record.json").write_text(json.dumps(record, indent=2))
    lock.unlink(missing_ok=True)
    print(f"\n=== arm={args.arm} status={record['status']} "
          f"wall={record['wall_seconds']}s figure={record['output_figure']} ===")
    print(json.dumps(record.get("score", {}), indent=2)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
