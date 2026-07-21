#!/usr/bin/env bash
#SBATCH --job-name=spatial-cellbench
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=2-00:00:00
#SBATCH --output=benchmark/spatial_cellbench/slurm/%x-%A_%a.out

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=${ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}
PYTHON=${PYTHON:-$HOME/miniconda3/envs/tissueagent/bin/python}
RUN_ROOT=${RUN_ROOT:-$ROOT/benchmark/spatial_cellbench/runs/formal_3paper_extension}
STAGE=${1:-generation}
RETRY_FAILED=${2:-}
PAPERS=(
  spcb_22b1a945e2
  spcb_fa0ad80e86
  spcb_783779446a
)

if [[ ! -x "$PYTHON" ]]; then
  echo "benchmark Python is not executable: $PYTHON" >&2
  exit 2
fi

if [[ "$STAGE" == "merge" ]]; then
  cd "$ROOT"
  export PYTHONPATH="$ROOT/src:$ROOT"
  "$PYTHON" -m benchmark.spatial_cellbench.run merge \
    --run-root "$RUN_ROOT" \
    --paper-id "${PAPERS[0]}" \
    --paper-id "${PAPERS[1]}" \
    --paper-id "${PAPERS[2]}"
  exit 0
fi
if [[ "$STAGE" != "preflight" && "$STAGE" != "generation" && "$STAGE" != "judge" ]]; then
  echo "stage must be preflight, generation, judge, or merge" >&2
  exit 2
fi
if [[ -n "$RETRY_FAILED" && "$RETRY_FAILED" != "--retry-failed" ]]; then
  echo "optional second argument must be --retry-failed" >&2
  exit 2
fi

TASK_ID=${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}
if (( TASK_ID < 0 || TASK_ID >= ${#PAPERS[@]} )); then
  echo "array task index is out of range: $TASK_ID" >&2
  exit 2
fi

cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export NUMBA_NUM_THREADS=2

PAPER_ID=${PAPERS[$TASK_ID]}
PAPER_RUN="$RUN_ROOT/papers/$PAPER_ID"
ARGS=(
  -m benchmark.spatial_cellbench.run run
  --run-dir "$PAPER_RUN"
  --paper-id "$PAPER_ID"
  --replicates 3
  --model o3-mini
  --orchestration-model gpt-5.1
  --judge-model gpt-4o
  --timeout 7200
)
if [[ "$RETRY_FAILED" == "--retry-failed" ]]; then
  ARGS+=(--retry-failed)
fi

if [[ "$STAGE" == "preflight" ]]; then
  "$PYTHON" -m benchmark.spatial_cellbench.validate_data \
    --archive papers-20260711T025044Z-2-001.zip \
    --archive papers-20260721T071755Z-1-001.zip
  "$PYTHON" "${ARGS[@]}" --validate-only
elif [[ "$STAGE" == "generation" ]]; then
  "$PYTHON" "${ARGS[@]}" --skip-judge
else
  "$PYTHON" "${ARGS[@]}"
fi
