#!/usr/bin/env bash
# Run ONE BioMysteryBench-Expression problem through TissueAgent (autopilot, --no-docker).
# Pulls the data zip via git-lfs if it's still an LFS pointer.
#
# Archives, per run: outputs/reports, the full terminal trace, the structured
# session trace (chat.json) and metrics.json (tokens, replans, step retries —
# see docs/benchmark-metrics-spec.md). The last two are NOT optional extras: the
# CLI wipes workspace/project/ at the start of every run, so anything left there
# is destroyed by the next problem.
#
# Usage: run_problem.sh <problem_id> "<prompt>"   [env: SEED=<label>]
set -uo pipefail

ID="$1"; PROMPT="$2"
SEED="${SEED:-0}"
ROOT=/work/magroup/wenduoc/TissueAgent
PY=/home/wenduoc/mambaforge/envs/tissueagent/bin/python
FULL="$ROOT/benchmark/biomysterybench/upstream"
ZIP="$FULL/data/$ID.zip"
DATASETS="$ROOT/workspace/library/datasets"
PROJECT_DIR="$ROOT/workspace/project"
OUTDIR="$PROJECT_DIR/outputs"
REPORTS="$ROOT/workspace/reports"
ARCHIVE="$ROOT/benchmark/biomysterybench/biomysterybench_expr/tissueagent_runs/$ID"

echo "=== [$ID] ensuring data present ==="
if [ ! -f "$ZIP" ] || [ "$(stat -c%s "$ZIP")" -lt 10000 ]; then
  echo "[$ID] data is an LFS pointer; pulling with git-lfs..."
  ( cd "$FULL" && git -c credential.helper='!f() { echo username=__token__; echo "password=$HF_TOKEN"; }; f' \
      lfs pull --include="data/$ID.zip" ) || { echo "[$ID] LFS pull FAILED"; exit 3; }
fi
[ -f "$ZIP" ] && [ "$(stat -c%s "$ZIP")" -ge 10000 ] || { echo "[$ID] no real data, aborting"; exit 3; }

echo "=== [$ID] preparing workspace ==="
rm -rf "$DATASETS"/* "$OUTDIR"/* "$REPORTS"/* 2>/dev/null || true
mkdir -p "$DATASETS" "$OUTDIR" "$REPORTS" "$ARCHIVE/reports" "$ARCHIVE/tables"
unzip -o -q "$ZIP" -d "$DATASETS"
ls -la "$DATASETS"

echo "=== [$ID] running TissueAgent (long) ==="
cd "$ROOT"
# The `2>&1` merge is load-bearing: the executor's per-cell logging goes to
# stderr, and the post-hoc miner reconstructs Layer-1 retries from it. Don't drop it.
PYTHONPATH=src "$PY" -m cli --no-docker \
  --task-id "$ID" --seed "$SEED" --metrics-out "$ARCHIVE/metrics.json" \
  "$PROMPT" 2>&1 | tee "$ARCHIVE/full_stdout.log"
rc=${PIPESTATUS[0]}

echo "=== [$ID] archiving (cli rc=$rc) ==="
cp -r "$OUTDIR"/. "$ARCHIVE/" 2>/dev/null || true
cp -r "$REPORTS"/. "$ARCHIVE/reports/" 2>/dev/null || true
# Structured session trace: messages, sub-agent transcripts, plan markdown,
# replan history. Written by save_session() to the active project dir, which
# the next run deletes — so copy it out now or lose it.
cp "$PROJECT_DIR/.chat.json" "$ARCHIVE/chat.json" 2>/dev/null \
  || echo "[$ID] WARNING: no .chat.json to archive"
[ -s "$ARCHIVE/metrics.json" ] || echo "[$ID] WARNING: no metrics.json (run died before the dump?)"
echo "=== [$ID] DONE rc=$rc -> $ARCHIVE ==="
exit "$rc"
