#!/usr/bin/env bash
#SBATCH --job-name=bmb-sweep
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=48:00:00
#SBATCH --output=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm/logs/sweep-%j.out
#
# Sweep (task × model × seed) through TissueAgent, one run at a time.
#
#     sbatch --export=ALL,TASKS="hb001 hb017",MODELS="gpt-5.1 claude-opus-4-7",SEEDS="0 1 2" run_sweep.sbatch
#
# TASKS defaults to every id in problems.csv; BUCKET=differential-expression
# narrows it to one bucket. SEEDS defaults to "0".
#
# SEQUENTIAL BY NECESSITY — every run shares workspace/ and kernel-gateway port
# 8888, so two concurrent runs (same node OR different nodes, since the
# workspace is on shared storage) destroy each other's inputs. Parallelising
# requires per-run workspace isolation and a per-run gateway port; until then,
# do not submit two of these at once. Use --dependency=afterany:<jobid>.
#
# RESUMABLE: a triple whose metrics.json already exists is skipped, so a
# timed-out or cancelled sweep can be resubmitted verbatim to finish the rest.
# Set FORCE=1 to re-run everything.
set -uo pipefail

BENCH=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr
DIR="$BENCH/slurm"
PY=/home/wenduoc/mambaforge/envs/tissueagent/bin/python

: "${MODELS:?set MODELS to a space-separated list of model ids, e.g. MODELS=\"gpt-5.1 claude-opus-4-7\"}"
SEEDS="${SEEDS:-0}"
BUCKET="${BUCKET:-}"
FORCE="${FORCE:-0}"

if [ -z "${TASKS:-}" ]; then
  TASKS="$("$PY" - "$BENCH/problems.csv" "$BUCKET" <<'PYEOF'
import csv, sys
path, bucket = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(path)))
if bucket:
    rows = [r for r in rows if r.get("bucket") == bucket]
print(" ".join(r["id"] for r in rows))
PYEOF
)"
fi

n_tasks=$(wc -w <<<"$TASKS"); n_models=$(wc -w <<<"$MODELS"); n_seeds=$(wc -w <<<"$SEEDS")
echo "host=$(hostname) job=${SLURM_JOB_ID:-none} start=$(date)"
echo "tasks=$n_tasks models=$n_models seeds=$n_seeds -> $((n_tasks * n_models * n_seeds)) runs"
echo "TASKS=[$TASKS]"; echo "MODELS=[$MODELS]"; echo "SEEDS=[$SEEDS]"

done_n=0; skipped=0; failed=0
for model in $MODELS; do
  for seed in $SEEDS; do
    for id in $TASKS; do
      slug="${model//\//__}"
      archive="$BENCH/runs/$slug/$id/$seed"
      if [ "$FORCE" != "1" ] && [ -s "$archive/metrics.json" ]; then
        echo "# SKIP $id|$model|seed=$seed (already has metrics.json)"
        skipped=$((skipped + 1))
        continue
      fi
      echo "############################################################"
      echo "# RUN $id | $model | seed=$seed  ($(date))"
      echo "############################################################"
      bash "$DIR/run_one.sh" "$id" "$model" "$seed"
      rc=$?
      [ "$rc" -eq 0 ] && done_n=$((done_n + 1)) || failed=$((failed + 1))
      echo "# $id|$model|seed=$seed exit=$rc"
    done
  done
done

echo "SWEEP DONE $(date) — ok=$done_n failed=$failed skipped=$skipped"
