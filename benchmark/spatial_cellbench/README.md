# Spatial CellBench

This benchmark asks a model to recover the analyses in twenty spatial-omics papers from frozen,
title-free scientific background. Public CellBench is used only as the protocol reference; its
single-cell dataset is not run here.

## Frozen design

The corpus contains twenty spatial-primary papers and 193 independently reported analyses. Each
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

Three replicates are averaged within each paper. The formal design is 20 papers x 3 arms x 3
replicates: 180 generation units and 180 judge units. Direct uses 60 model calls, judging uses
1,737 candidate-level calls, and native TA call counts depend on its plans. Every TA+CV unit
includes the corresponding 3N CV calls, totaling 1,737 across all twenty papers. The experiment
is a descriptive benchmark.

## Results

Three aggregates are tracked under `results/`. All use protocol `spatial_cellbench_dynamic_n_v2`,
`o3-mini` generation, `gpt-5.1` orchestration, the arm-blind `gpt-4o` judge, three replicates, and
a 10,000-sample paired paper bootstrap with seed 20260720. Arm values are mean paper hit
fractions; contrasts are percentage points with paired 95% intervals.

| Aggregate | Papers | Direct | TA | TA+CV | TA - Direct | TA+CV - TA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `formal_aggregate.json` (historical) | 11 | 46.21% | 47.24% | 55.08% | +1.03 [-2.92, +4.90] | +7.84 [-3.09, +17.64] |
| `formal_9paper_extension/aggregate.json` | 9 | 67.59% | 65.30% | 79.71% | -2.29 [-10.08, +5.40] | +14.41 [+5.74, +21.86] |
| `combined_20paper_aggregate.json` | 20 | 55.83% | 55.37% | 66.16% | -0.46 [-4.69, +3.63] | +10.80 [+3.35, +17.32] |

Every scheduled unit succeeded (180 generation and 180 judge units across all twenty papers). The
combined aggregate pools three frozen source batches with different source fingerprints, exactly
as the historical eleven-paper aggregate pools its eight- and three-paper batches; its
`source_batches` field records each batch's fingerprint, commit, and checkpoint hash. It is a
descriptive cross-batch summary, not a single-fingerprint rerun. Paper-level tables, cost, and
integrity checks are in `docs/spatial_cellbench_results.md`. The nine-paper run's exact commands,
timeline, incidents, and verification steps are in `results/formal_9paper_extension/PROVENANCE.md`.

## Validate

```bash
python -m benchmark.spatial_cellbench.validate_data \
  --archive papers-20260711T025044Z-2-001.zip \
  --archive papers-20260721T071755Z-1-001.zip \
  --archive papers-20260902T-extension-001.zip

python -m benchmark.spatial_cellbench.run run \
  --run-dir /tmp/spatial-cellbench-check --validate-only
```

Checkpoints are immutable and resumable. `--skip-judge` stages generation first;
`--retry-failed` retries only failed units in a new attempt directory.

## CPU Slurm run

The launcher runs all twenty papers, one per CPU node. Submit the stages with dependencies so
generation and judging never write the same checkpoint concurrently:

```bash
GEN_JOB=$(sbatch --parsable --array=0-19%3 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh generation)
JUDGE_JOB=$(sbatch --parsable --dependency=afterok:${GEN_JOB} --array=0-19%3 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh judge)
sbatch --dependency=afterok:${JUDGE_JOB} --array=0 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh merge
```

The default run root is `benchmark/spatial_cellbench/runs/formal_20paper`. Set `RUN_ROOT`
to use a different immutable run directory. The launcher defaults to the local `tissueagent`
Conda environment; set `PYTHON` to override it. Submit from the repository root. Do not combine
checkpoints from another source fingerprint inside one resumable run directory.

Set `PAPER_SET=extension` to run only the nine added papers; its default run root is
`runs/formal_9paper_extension`. The exact estimands and contrasts are frozen in `analysis_spec.md`.
Runtime checkpoints stay under the ignored run root; the committed nine-paper checkpoints are
copied under `results/formal_9paper_extension/papers/`.

The source fingerprint hashes this README and every other top-level `*.md` and `*.py` file in this
directory, so documentation edits after a run change it. Commit `4716b53` is fingerprint-identical
to the nine-paper run; resume, re-judge, or re-merge that run from that commit.

The paper archives are not tracked in git. Their sha256 hashes are in `data/corpus_manifest.json`,
and source DOIs and PMCIDs are in `data/source_records/`. Generation and judging read only the
frozen JSON under `data/`; the archives are needed only for the PDF check in `validate_data`.
