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
ROOT=${ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}}
PYTHON=${PYTHON:-$HOME/miniconda3/envs/tissueagent/bin/python}
PAPER_SET=${PAPER_SET:-all}
STAGE=${1:-generation}
RETRY_FAILED=${2:-}
if [[ "$PAPER_SET" == "all" ]]; then
  RUN_ROOT=${RUN_ROOT:-$ROOT/benchmark/spatial_cellbench/runs/formal_20paper}
  PAPERS=(
    spcb_f4c0753473
    spcb_7e74c983be
    spcb_5940c8e4ea
    spcb_b4769977eb
    spcb_4e967b72a1
    spcb_732f7ca9d3
    spcb_377c86462b
    spcb_3d9b1bdbd6
    spcb_22b1a945e2
    spcb_fa0ad80e86
    spcb_783779446a
    spcb_9f3a1c7d20
    spcb_a10b2c3d4e
    spcb_b20c3d4e5f
    spcb_c30d4e5f6a
    spcb_d40e5f6a7b
    spcb_e50f6a7b8c
    spcb_f60a7b8c9d
    spcb_07b8c9d0e1
    spcb_18c9d0e1f2
  )
elif [[ "$PAPER_SET" == "extension" ]]; then
  RUN_ROOT=${RUN_ROOT:-$ROOT/benchmark/spatial_cellbench/runs/formal_9paper_extension}
  PAPERS=(
    spcb_9f3a1c7d20
    spcb_a10b2c3d4e
    spcb_b20c3d4e5f
    spcb_c30d4e5f6a
    spcb_d40e5f6a7b
    spcb_e50f6a7b8c
    spcb_f60a7b8c9d
    spcb_07b8c9d0e1
    spcb_18c9d0e1f2
  )
else
  echo "PAPER_SET must be all or extension: $PAPER_SET" >&2
  exit 2
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "benchmark Python is not executable: $PYTHON" >&2
  exit 2
fi

if [[ "$STAGE" == "merge" ]]; then
  cd "$ROOT"
  export PYTHONPATH="$ROOT/src:$ROOT"
  MERGE_ARGS=(
    -m benchmark.spatial_cellbench.run merge
    --run-root "$RUN_ROOT"
  )
  for paper_id in "${PAPERS[@]}"; do
    MERGE_ARGS+=(--paper-id "$paper_id")
  done
  "$PYTHON" "${MERGE_ARGS[@]}"
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
    --archive papers-20260721T071755Z-1-001.zip \
    --archive papers-20260902T-extension-001.zip
  "$PYTHON" "${ARGS[@]}" --validate-only
elif [[ "$STAGE" == "generation" ]]; then
  "$PYTHON" "${ARGS[@]}" --skip-judge
else
  "$PYTHON" "${ARGS[@]}"
fi
