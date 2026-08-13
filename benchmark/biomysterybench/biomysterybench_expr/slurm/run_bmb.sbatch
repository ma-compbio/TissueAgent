#!/usr/bin/env bash
#SBATCH --job-name=bmb-expr
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm/logs/bmb-%j.out
#
# Run a list of BioMysteryBench-Expression problems through TissueAgent, one at a
# time (they share the single workspace/ + kernel-gateway port 8888, so SEQUENTIAL
# only within a job). Pass ids via the IDS env var:
#
#     sbatch --export=ALL,IDS="hb001 hb006" run_bmb.sbatch
#
# For parallelism, submit multiple jobs on DISTINCT nodes (one gateway per node);
# same-node concurrency collides on port 8888 — see README notes.
set -uo pipefail
DIR=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm
PY=/home/wenduoc/mambaforge/envs/tissueagent/bin/python

: "${IDS:?set IDS to a space-separated list of problem ids, e.g. IDS=\"hb001 hb006\"}"
echo "host=$(hostname)  job=$SLURM_JOB_ID  ids=[$IDS]  start=$(date)"

for id in $IDS; do
  echo "############################################################"
  echo "# PROBLEM $id  ($(date))"
  echo "############################################################"
  prompt="$("$PY" "$DIR/make_prompt.py" "$id")" || { echo "prompt gen failed for $id"; continue; }
  bash "$DIR/run_problem.sh" "$id" "$prompt"
  echo "# $id exit=$?"
done
echo "ALL DONE $(date)"
