#!/usr/bin/env bash
# Run ONE (task, model, seed) triple through TissueAgent (autopilot, --no-docker).
#
# Supersedes run_problem.sh for sweeps. The difference that matters is the
# archive path: run_problem.sh writes to tissueagent_runs/<id>/, which has no
# model or seed dimension, so a second seed silently overwrites the first.
# Here every run gets its own directory:
#
#     runs/<model_id>/<task_id>/<seed>/
#       metrics.json      structured dump (tokens, replans, retries, runtime)
#       chat.json         full graph conversation + sub-agent transcripts
#       full_stdout.log   terminal trace (the `2>&1` merge is load-bearing —
#                         the Layer-1 miner reconstructs executor retries from it)
#       answer.txt        final answer, for the grader
#       attempts.jsonl    one line per launch (see below)
#       outputs/…         archived artifacts
#
# TRIALS ARE TWO DIFFERENT THINGS; both are recorded.
#   seed    — a replicate. Same task, same model, different sampling. Varying it
#             is what makes pass@1 / pass@k computable; a single seed cannot
#             separate a real capability from a lucky draw.
#   attempt — a re-launch of one (task, model, seed) because the previous launch
#             produced no result: a hung kernel, a crash, a cancelled job. This
#             is infrastructure noise, NOT another sample of the model, and
#             pooling it into the seed count would inflate pass@k with retries.
#
# Every launch appends to attempts.jsonl and passes --attempt N to the CLI, so
# metrics.json carries the count that produced it. The 2026-07-25 v0 sweep is
# why this exists: one task hung for 3h17m on its first code cell and the whole
# sequential sweep stalled behind it with nothing recorded.
#
# Usage: run_one.sh <task_id> <model_id> <seed>
#   env: HF_TOKEN     for git-lfs pulls of the data zips
#        TIMEOUT_S    wall-clock cap per launch (default 5400 = 90 min; the v0 sweep's
#                     slowest completed run was 1341s, so this is ~4x headroom).
#                     A launch killed by it exits 124 and is logged as timeout.
set -uo pipefail

ID="$1"; MODEL="$2"; SEED="$3"
ROOT=/work/magroup/wenduoc/TissueAgent
PY=/home/wenduoc/mambaforge/envs/tissueagent/bin/python
BENCH="$ROOT/benchmark/biomysterybench/biomysterybench_expr"
FULL="$ROOT/benchmark/biomysterybench/upstream"
ZIP="$FULL/data/$ID.zip"

# STATE_ROOT holds this worker's mutable state (workspace/, projects/,
# plan_scratch/). Defaults to the repo root, which is the single-worker
# behaviour. run_shard.sbatch gives each concurrent worker its own, because the
# `rm -rf "$DATASETS"/*` below would otherwise delete a peer's inputs mid-run.
# TISSUEAGENT_GATEWAY_PORT must be distinct per worker for the same reason.
STATE_ROOT="${TISSUEAGENT_STATE_ROOT:-$ROOT}"
export TISSUEAGENT_STATE_ROOT="$STATE_ROOT"
export TISSUEAGENT_GATEWAY_PORT="${TISSUEAGENT_GATEWAY_PORT:-8888}"

DATASETS="$STATE_ROOT/workspace/library/datasets"
PROJECT_DIR="$STATE_ROOT/workspace/project"
OUTDIR="$PROJECT_DIR/outputs"
REPORTS="$STATE_ROOT/workspace/reports"

# Model ids contain '/' (openrouter/gpt-5.1) — flatten so it stays one level.
MODEL_SLUG="${MODEL//\//__}"
ARCHIVE="$BENCH/runs/$MODEL_SLUG/$ID/$SEED"

echo "=== [$ID|$MODEL|seed=$SEED] ensuring data present ==="
if [ ! -f "$ZIP" ] || [ "$(stat -c%s "$ZIP")" -lt 10000 ]; then
  echo "[$ID] data is an LFS pointer; pulling with git-lfs..."
  ( cd "$FULL" && git -c credential.helper='!f() { echo username=__token__; echo "password=$HF_TOKEN"; }; f' \
      lfs pull --include="data/$ID.zip" ) || { echo "[$ID] LFS pull FAILED"; exit 3; }
fi
[ -f "$ZIP" ] && [ "$(stat -c%s "$ZIP")" -ge 10000 ] || { echo "[$ID] no real data, aborting"; exit 3; }

echo "=== [$ID|$MODEL|seed=$SEED] preparing workspace ==="
rm -rf "$DATASETS"/* "$OUTDIR"/* "$REPORTS"/* 2>/dev/null || true
mkdir -p "$DATASETS" "$OUTDIR" "$REPORTS" "$ARCHIVE/reports" "$ARCHIVE/tables"
unzip -o -q "$ZIP" -d "$DATASETS"

prompt="$("$PY" "$BENCH/slurm/make_prompt.py" "$ID")" || { echo "[$ID] prompt gen failed"; exit 4; }

# Attempt number = prior launches + 1. attempts.jsonl is append-only and is the
# only record that survives a re-launch, since metrics.json and full_stdout.log
# are overwritten by the next attempt.
ATTEMPTS_LOG="$ARCHIVE/attempts.jsonl"
ATTEMPT=1
[ -f "$ATTEMPTS_LOG" ] && ATTEMPT=$(( $(wc -l < "$ATTEMPTS_LOG") + 1 ))
TIMEOUT_S="${TIMEOUT_S:-5400}"

echo "=== [$ID|$MODEL|seed=$SEED] running TissueAgent (attempt $ATTEMPT, timeout ${TIMEOUT_S}s) ==="
cd "$ROOT"
started_at="$(date -Iseconds)"; t0=$SECONDS
# `timeout` so a hung kernel cannot stall the whole sequential sweep: TERM at the
# cap, KILL 60s later if it ignores TERM. rc 124 == timed out.
PYTHONPATH=src timeout --signal=TERM --kill-after=60 "$TIMEOUT_S" "$PY" -m cli --no-docker \
  --model "$MODEL" --task-id "$ID" --seed "$SEED" --attempt "$ATTEMPT" \
  --metrics-out "$ARCHIVE/metrics.json" \
  "$prompt" 2>&1 | tee "$ARCHIVE/full_stdout.log"
rc=${PIPESTATUS[0]}
elapsed=$(( SECONDS - t0 ))
[ "$rc" -eq 124 ] && echo "[$ID] TIMEOUT after ${TIMEOUT_S}s — killed, moving on"

echo "=== [$ID|$MODEL|seed=$SEED] archiving (cli rc=$rc) ==="
cp -r "$OUTDIR"/. "$ARCHIVE/" 2>/dev/null || true
cp -r "$REPORTS"/. "$ARCHIVE/reports/" 2>/dev/null || true
# The CLI wipes workspace/project/ at the start of every run, so the structured
# trace has to be copied out now or the next run destroys it.
cp "$PROJECT_DIR/.chat.json" "$ARCHIVE/chat.json" 2>/dev/null \
  || echo "[$ID] WARNING: no .chat.json to archive"
[ -s "$ARCHIVE/metrics.json" ] || echo "[$ID] WARNING: no metrics.json (run died before the dump?)"

# answer.txt: the grader reads this rather than re-parsing the log.
"$PY" - "$ARCHIVE" <<'PYEOF' || echo "[$ID] WARNING: could not write answer.txt"
import json, sys
from pathlib import Path
archive = Path(sys.argv[1])
try:
    answer = json.loads((archive / "metrics.json").read_text())["outcome"]["final_answer"]
except Exception:
    answer = ""
(archive / "answer.txt").write_text(answer, encoding="utf-8")
PYEOF

# Ledger line for this launch. Written last so it can record what the run
# actually produced; `outcome` is the harness's verdict, independent of the
# grader — "completed" here means a result exists to grade, nothing more.
"$PY" - "$ARCHIVE" "$ATTEMPT" "$started_at" "$elapsed" "$rc" "$TIMEOUT_S" <<'PYEOF' \
  || echo "[$ID] WARNING: could not append attempts.jsonl"
import json, sys
from pathlib import Path

archive, attempt, started_at, elapsed, rc, timeout_s = sys.argv[1:7]
metrics = Path(archive) / "metrics.json"
terminal = None
try:
    terminal = json.loads(metrics.read_text())["outcome"].get("terminal_state")
except Exception:
    pass

rc = int(rc)
if rc == 124:
    outcome = "timeout"
elif not metrics.is_file() or metrics.stat().st_size == 0:
    outcome = "no-result"          # crashed or killed before the metrics dump
elif rc != 0:
    outcome = "nonzero-exit"
else:
    outcome = "completed"

with open(Path(archive) / "attempts.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "attempt": int(attempt),
        "started_at": started_at,
        "wall_time_s": int(elapsed),
        "exit_code": rc,
        "outcome": outcome,
        "terminal_state": terminal,
        "timeout_s": int(timeout_s),
    }) + "\n")
print(f"[attempt {attempt}] {outcome} rc={rc} {elapsed}s")
PYEOF

echo "=== [$ID|$MODEL|seed=$SEED] DONE rc=$rc attempt=$ATTEMPT -> $ARCHIVE ==="
exit "$rc"
