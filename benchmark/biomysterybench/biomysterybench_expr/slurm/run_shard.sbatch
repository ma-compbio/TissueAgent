#!/usr/bin/env bash
#SBATCH --job-name=bmb-shard
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=24:00:00
# %j only — %a is the array task id and expands to 4294967294 on a non-array
# job, which is how these are submitted. The worker index is in the log body.
#SBATCH --output=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm/logs/shard-%j.out
#
# Run ONE SHARD of tasks. Several of these run CONCURRENTLY — this is the
# parallel counterpart to run_sweep.sbatch, which is sequential.
#
#     sbatch --export=ALL,MODELS="gpt-5.1",TASKS="hb001 hb003 hb016 hb022",WORKER=1 run_shard.sbatch
#     sbatch --export=ALL,MODELS="gpt-5.1",TASKS="hb026 hb027 hb029 hb030",WORKER=2 run_shard.sbatch
#
# WHY THIS IS SAFE WHEN run_sweep.sbatch SAID PARALLELISING WAS NOT.
# The old warning was accurate: every run shared workspace/ and gateway port
# 8888, so concurrent runs deleted each other's datasets and fought over
# kernels. Two things now make workers independent, and BOTH are required:
#
#   1. TISSUEAGENT_STATE_ROOT — each worker gets its own workspace/, projects/
#      and plan_scratch/ under .bench_workers/w<N>/. run_one.sh wipes
#      workspace/library/datasets/ before every run; without this, worker 2's
#      wipe destroys worker 1's inputs mid-run.
#   2. TISSUEAGENT_GATEWAY_PORT — one Jupyter Kernel Gateway per worker
#      (8888 + WORKER). Sharing a port is worse than a bind failure: the second
#      worker would attach to the first's kernels and run its code in the wrong
#      workspace, producing plausible results from the wrong data.
#
# Shards must be DISJOINT. Two workers given the same task id write the same
# archive directory and corrupt each other's attempts.jsonl.
#
#   env: MODELS   space-separated model ids (required)
#        TASKS    space-separated task ids for THIS shard (required)
#        WORKER   integer >=1, unique per concurrent shard (required)
#        SEED     seed label, or "random" for one random label per task
#                 (default: random). NOTE: the seed is a *label only* — it is
#                 recorded in metrics.json and never reaches the model call, so
#                 it does not make a run reproducible. Replicate-to-replicate
#                 variation comes from API nondeterminism.
#        FORCE    1 = re-run tasks that already have metrics.json
#        TIMEOUT_S per-launch wall-clock cap (default 5400, see run_one.sh)
set -uo pipefail

ROOT=/work/magroup/wenduoc/TissueAgent
BENCH="$ROOT/benchmark/biomysterybench/biomysterybench_expr"
DIR="$BENCH/slurm"

: "${MODELS:?set MODELS, e.g. MODELS=\"gpt-5.1\"}"
: "${TASKS:?set TASKS to the task ids for this shard}"
: "${WORKER:?set WORKER to a unique integer >=1 per concurrent shard}"
SEED="${SEED:-random}"
FORCE="${FORCE:-0}"

export TISSUEAGENT_STATE_ROOT="$ROOT/.bench_workers/w$WORKER"
export TISSUEAGENT_GATEWAY_PORT=$((8888 + WORKER))

# Refuse to start if this worker's port is already live — that means another
# shard is using this WORKER index, and proceeding would cross the streams.
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$TISSUEAGENT_GATEWAY_PORT "; then
  echo "FATAL: port $TISSUEAGENT_GATEWAY_PORT already in use — WORKER=$WORKER is taken. Pick another."
  exit 2
fi

mkdir -p "$TISSUEAGENT_STATE_ROOT/workspace/library/datasets" \
         "$TISSUEAGENT_STATE_ROOT/workspace/library/files" \
         "$TISSUEAGENT_STATE_ROOT/workspace/project/outputs" \
         "$TISSUEAGENT_STATE_ROOT/workspace/project/uploads" \
         "$TISSUEAGENT_STATE_ROOT/workspace/reports" \
         "$TISSUEAGENT_STATE_ROOT/projects" \
         "$TISSUEAGENT_STATE_ROOT/plan_scratch"

n_tasks=$(wc -w <<<"$TASKS")
echo "host=$(hostname) job=${SLURM_JOB_ID:-none} worker=$WORKER start=$(date)"
echo "state_root=$TISSUEAGENT_STATE_ROOT gateway_port=$TISSUEAGENT_GATEWAY_PORT"
echo "tasks=$n_tasks models=$(wc -w <<<"$MODELS") seed=$SEED"
echo "TASKS=[$TASKS]"

done_n=0; skipped=0; failed=0
for model in $MODELS; do
  for id in $TASKS; do
    if [ "$SEED" = "random" ]; then seed=$RANDOM; else seed="$SEED"; fi
    slug="${model//\//__}"
    archive="$BENCH/runs/$slug/$id/$seed"
    # Skip only on an existing result for this exact triple. A random seed makes
    # the path new every time, so FORCE is rarely needed with SEED=random —
    # which also means a resubmit re-runs everything. Pin SEED to resume.
    if [ "$FORCE" != "1" ] && [ -s "$archive/metrics.json" ]; then
      echo "# SKIP $id|$model|seed=$seed (already has metrics.json)"
      skipped=$((skipped + 1)); continue
    fi
    echo "############################################################"
    echo "# RUN $id | $model | seed=$seed | worker=$WORKER  ($(date))"
    echo "############################################################"
    bash "$DIR/run_one.sh" "$id" "$model" "$seed"
    rc=$?
    [ "$rc" -eq 0 ] && done_n=$((done_n + 1)) || failed=$((failed + 1))
    echo "# $id|$model|seed=$seed exit=$rc"
  done
done

echo "SHARD $WORKER DONE $(date) — ok=$done_n failed=$failed skipped=$skipped"
