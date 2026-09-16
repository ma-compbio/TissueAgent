#!/usr/bin/env bash
# Submit replicate seeds 1 and 2 for the whole 20-task BMB-Expr subset on gpt-5.1.
#
# Seed 0 (2026-07-28, jobs 54199-54205) is single-replicate, so pass@1 / pass@k
# are not computable from it. Two more seeds make k=3.
#
# EIGHT CONCURRENT SHARDS: the 20 tasks are split into 4 disjoint bins, and both
# seeds run at once (4 bins x 2 seeds). Bins are balanced by seed-0 wall time,
# not task count, so the longest task doesn't serialise a whole bin behind it —
# hb001 (timed out at the 5400s cap) is budgeted as 90 min and gets the lightest
# bin. Expect ~110 min per shard.
#
# Sizing against the single cpu node (oven-0-25: 128 CPUs, 515G): 8 x 8 CPUs =
# 64 and 8 x 48G = 384G, on top of whatever is already allocated. Do not raise
# the shard count without re-checking `scontrol show node` — overcommitting
# memory here is what makes runs die mid-analysis with no metrics.json.
#
# WORKER indices 201-208 are fresh: each maps to gateway port 8888+WORKER
# (9089-9096) and state root .bench_workers/w<N>/, and reusing an index that a
# live shard holds would cross two runs onto one kernel. Prior sweeps consumed
# 1-6, 11-18, 21-28, 41, 51-58, 61-68, 81-88, 101-107.
#
# SEED is pinned (not "random") so a resubmit skips triples that already have
# metrics.json and resumes the rest.
set -uo pipefail

DIR=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm
MODEL="${MODELS:-gpt-5.1}"

# Bin -> tasks. Union is exactly the 20 ids in manifest.csv; bins are disjoint,
# which run_shard.sbatch requires (same id in two shards corrupts attempts.jsonl).
BIN_A="hb001 recvnlq3i6id6qqge reci6iglwiertmyyk"
BIN_B="rec35farlwqz6kmy7 recaikavdwoimjy3b hb003 hb029 hb016"
BIN_C="hb039 rec5xuqc70ithi19c hb033 hb043 hb017 recvwctg0xadnklms"
BIN_D="rece8yuamgclcpj9i recav6jt6q0aa9sjs hb052 recx4bsaa5zoxy3nv hb030 rec4kcr3oroe3jc1j"

worker=201
for seed in 1 2; do
  for bin in A B C D; do
    eval "tasks=\$BIN_$bin"
    jid=$(sbatch --parsable \
      --job-name="bmb-s${seed}${bin}" \
      --export=ALL,MODELS="$MODEL",TASKS="$tasks",WORKER="$worker",SEED="$seed" \
      "$DIR/run_shard.sbatch")
    echo "seed=$seed bin=$bin worker=$worker job=$jid tasks=$(wc -w <<<"$tasks")"
    worker=$((worker + 1))
  done
done
