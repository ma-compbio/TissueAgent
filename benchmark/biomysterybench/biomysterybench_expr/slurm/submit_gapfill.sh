#!/usr/bin/env bash
# Fill the 11 empty cells in the 20-task x 3-seed BMB-Expr grid on gpt-5.1.
#
# WHAT WAS ACTUALLY LOST, AND WHY. The seed-1/2 sweep (2026-07-30, jobs
# 55229-55236) reported ok=29 failed=11. Every one of those 11 exited 124 —
# run_one.sh:92 wraps the CLI in `timeout --signal=TERM --kill-after=60
# $TIMEOUT_S`, and 124 is that cap firing. None were lost to memory.
#
# Three shards (55229, 55230, 55234) do log `oom-kill ... in StepId=N.batch
# cgroup`, and that is a real per-shard breach of the 48G request rather than
# node contention — but it is not what cost us the runs. The losses do not track
# it: 55232 took an OOM and still went 6/6, while 55231 and 55235 took none and
# lost 2 and 3. Memory is raised below anyway, on the theory that a kernel killed
# mid-analysis is one way an agent ends up looping until the cap; it is a
# hedge, not the diagnosis.
#
# Nor was it a concurrency slowdown. Paired against seed 0 over the 29 runs that
# have both, the median wall time is flat: 1014s -> 1008s.
#
# The cap is not tight. The slowest SUCCESSFUL run in all 49 is hb039/1 at
# 3708s, well under 5400. What times out is per-task variance of a different
# order — hb003 and recvnlq3i6id6qqge each finish in ~800-950s on seed 0 and
# then blow through 90 min on BOTH retries. That is a runaway agent loop, the
# same failure family as hb017/2 terminating at RECURSION_LIMIT=100. So
# TIMEOUT_S stays 5400 deliberately: raising it would buy tokens spent looping,
# not answers. Cells that time out again are a property of the task, and should
# be reported as such rather than papered over.
#
# RESUME IS THE MECHANISM, NOT A RE-RUN. run_shard.sbatch:89 skips any triple
# that already has a non-empty metrics.json, so SEED must be pinned (a "random"
# label makes every archive path new and re-runs the whole shard). The TASKS
# lists below are already narrowed to the gaps; the skip is the safety net if
# this is submitted twice.
#
# DISJOINTNESS. Shards must not collide on an archive dir, which is
# runs/<model>/<task>/<seed> (run_one.sh:62) — so the unique key is the (task,
# seed) PAIR, not the task. hb001 and hb003 each appear in two shards below
# under different seeds and write different directories; this is the same shape
# as submit_seeds_1_2.sh running identical bins for seeds 1 and 2 at once.
#
# SIZING. 3 x 8 CPUs = 24 and 3 x 96G = 288G, against oven-0-25's 58 idle CPUs
# and ~160G free at submit time — so these will spread across the cpu partition
# rather than stack. Memory is doubled from the 48G that the three shards above
# breached. Do not fold these into fewer shards: seed 1 carries 6 tasks and, at
# the 5400s cap, a worst case near 9h serial.
#
# WORKER indices 221-223 are fresh (ports 9109-9111 confirmed free). Consumed so
# far: 1-6, 11-18, 21-28, 41, 51-58, 61-68, 81-88, 101-107, 201-208 — and 212 is
# NOT usable, port 9100 was already listening.
set -uo pipefail

DIR=/work/magroup/wenduoc/TissueAgent/benchmark/biomysterybench/biomysterybench_expr/slurm
MODEL="${MODELS:-gpt-5.1}"
MEM="${MEM:-96G}"
TIMEOUT_S="${TIMEOUT_S:-5400}"

# seed -> the cells missing for that seed. Union is 11, matching the 11 exit=124
# failures. hb001/0 is included: it timed out in the ORIGINAL 2026-07-28 sweep,
# which is why seed 0 grades 19 tasks and not 20.
SEED_0="hb001"
SEED_1="hb001 hb003 hb017 rec35farlwqz6kmy7 rec5xuqc70ithi19c recvnlq3i6id6qqge"
SEED_2="hb003 hb033 recvwctg0xadnklms recvnlq3i6id6qqge"

worker=221
for seed in 0 1 2; do
  eval "tasks=\$SEED_$seed"
  jid=$(sbatch --parsable \
    --job-name="bmb-gap-s${seed}" \
    --mem="$MEM" \
    --export=ALL,MODELS="$MODEL",TASKS="$tasks",WORKER="$worker",SEED="$seed",TIMEOUT_S="$TIMEOUT_S" \
    "$DIR/run_shard.sbatch")
  echo "seed=$seed worker=$worker job=$jid tasks=$(wc -w <<<"$tasks")  [$tasks]"
  worker=$((worker + 1))
done
