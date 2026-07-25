# Spatial CellBench

This benchmark asks a model to recover the analyses in eleven spatial-omics papers from frozen,
title-free scientific background. Public CellBench is used only as the protocol reference; its
single-cell dataset is not run here.

## Frozen design

The corpus contains eleven spatial-primary papers and 112 independently reported analyses. Each
paper's true analysis count is disclosed to every generation arm, matching CellBench's oracle-N
setup. Counts range from 5 to 12.

The three arms are:

1. `direct`: one o3-mini call requesting N analyses;
2. `tissueagent`: the native Planner -> Recruiter -> Manager -> Evaluator -> Reporter graph with
   Hypothesis and Critic as its domain roster;
3. `tissueagent_spatial_cv`: the same native graph with Spatial-CV added to the roster and the
   draft step explicitly assigned to it through the normal Recruiter output.

TA+CV is a method-compliance treatment: it must recruit Spatial-CV for the draft, produce its
audited protocol bundle, and expose that bundle to final Hypothesis synthesis. Otherwise the unit
fails rather than being scored as TA+CV. Its task differs from TA only by this paper-independent
agent assignment. Production Planner, Recruiter, Manager, Evaluator, Reporter, and graph code are
unchanged.

Candidate-generating workers use `o3-mini` with medium reasoning. In the native arms, the
production outer Planner, Recruiter, Manager, Evaluator, and Reporter use TissueAgent's default
orchestration model, `gpt-5.1`; Hypothesis, Critic, and a recruited Spatial-CV remain o3-mini
workers. An arm-blind `gpt-4o` judge evaluates each candidate independently against the complete
hidden truth set. Multiple candidates may match the same truth item, exactly as in upstream
CellBench. The primary per-paper value is therefore the candidate hit fraction, not one-to-one
precision, truth recall, ARI, NMI, or F1.

Three replicates are averaged within each paper. The formal design is 11 papers x 3 arms x 3
replicates: 99 generation units and 99 judge units. Direct uses 33 model calls, judging uses
1,008 candidate-level calls, and native TA call counts depend on its plans. Every TA+CV unit
includes the corresponding 3N CV calls, totaling 1,008 across all eleven papers. The experiment
is a descriptive benchmark.

## Validate

```bash
python -m benchmark.spatial_cellbench.validate_data \
  --archive papers-20260711T025044Z-2-001.zip \
  --archive papers-20260721T071755Z-1-001.zip

python -m benchmark.spatial_cellbench.run run \
  --run-dir /tmp/spatial-cellbench-check --validate-only
```

Checkpoints are immutable and resumable. `--skip-judge` stages generation first;
`--retry-failed` retries only failed units in a new attempt directory.

## CPU Slurm run

The completed eight papers are not rerun. The launcher contains only the three extension papers,
one per CPU node. Submit the stages with dependencies so generation and judging never write the
same checkpoint concurrently:

```bash
GEN_JOB=$(sbatch --parsable --array=0-2 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh generation)
JUDGE_JOB=$(sbatch --parsable --dependency=afterok:${GEN_JOB} --array=0-2 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh judge)
sbatch --dependency=afterok:${JUDGE_JOB} --array=0 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh merge
```

The default run root is `benchmark/spatial_cellbench/runs/formal_3paper_extension`. Set `RUN_ROOT`
to use a different immutable run directory. The launcher defaults to the local `tissueagent`
Conda environment; set `PYTHON` to override it. Submit from the repository root. Do not combine
checkpoints from another source fingerprint inside one resumable run directory.

The exact estimands and contrasts are frozen in `analysis_spec.md`. The tracked formal aggregate
under `results/` contains all eleven papers and records the eight-paper and three-paper source
batches separately. Runtime checkpoints stay under the ignored run root.
