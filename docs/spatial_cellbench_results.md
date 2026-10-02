# Spatial CellBench formal results

_Twenty spatial papers in three frozen source batches, three replicates per method. The
eleven-paper result was completed 2026-07-21 and the nine-paper extension on 2026-09-03._

## Summary

Values are mean paper hit fractions: candidate hit fractions averaged over the three replicates
within each paper, then over papers. Contrasts are percentage points with 10,000-sample paired
paper bootstrap 95% intervals (seed 20260720).

| Aggregate | Papers | Direct | TA | TA+CV | TA - Direct | TA+CV - TA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Eleven-paper (historical) | 11 | 46.21% | 47.24% | 55.08% | +1.03 [-2.92, +4.90] | +7.84 [-3.09, +17.64] |
| Nine-paper extension | 9 | 67.59% | 65.30% | **79.71%** | -2.29 [-10.08, +5.40] | +14.41 [+5.74, +21.86] |
| Twenty-paper combined | 20 | 55.83% | 55.37% | **66.16%** | -0.46 [-4.69, +3.63] | +10.80 [+3.35, +17.32] |

All 180 generation and 180 judge units completed. The combined row pools three source batches
with different source fingerprints, exactly as the eleven-paper aggregate already pools its eight-
and three-paper batches, so it is a descriptive cross-batch summary rather than a single-fingerprint
rerun. The nine added papers score higher than the original eleven under every arm, so batch
composition shifts the combined means; the paired contrasts compare arms within each paper.

## Nine-paper extension

GraphST, STAGATE, SOTIP, SpaceFlow, SpotClean, Squidpy, SEDR, stLearn, and MERINGUE contribute
81 analysis labels, 8 to 10 per paper.

| Method | Mean paper hit fraction | Pooled hit fraction | Complete units |
| --- | ---: | ---: | ---: |
| Direct | 67.59% | 67.08% | 27/27 |
| TA | 65.30% | 65.02% | 27/27 |
| TA+CV | **79.71%** | **79.42%** | 27/27 |

| Contrast | Estimate | Paired 95% interval | Papers |
| --- | ---: | ---: | ---: |
| TA - Direct | -2.29 points | [-10.08, +5.40] | 9 |
| TA+CV - TA | +14.41 points | [+5.74, +21.86] | 9 |

TA+CV beat TA on seven papers, tied on stLearn, and lost on SpotClean. TA beat Direct on four
papers, tied on SpotClean, and lost on four. With nine papers this remains a descriptive result.

### Paper-level results

Values are mean candidate hit fractions across three replicates.

| Paper | Analyses | Direct | TA | TA+CV |
| --- | ---: | ---: | ---: | ---: |
| GraphST | 10 | 60.00% | 40.00% | **66.67%** |
| STAGATE | 9 | 55.56% | 74.07% | **88.89%** |
| SOTIP | 10 | 60.00% | 63.33% | **73.33%** |
| SpaceFlow | 9 | 70.37% | 77.78% | **100.00%** |
| SpotClean | 8 | **75.00%** | **75.00%** | 62.50% |
| Squidpy | 8 | 75.00% | 62.50% | **91.67%** |
| SEDR | 8 | 75.00% | 58.33% | **79.17%** |
| stLearn | 10 | 63.33% | **70.00%** | **70.00%** |
| MERINGUE | 9 | 74.07% | 66.67% | **85.19%** |

### Cost and integrity

| Method | Mean model calls per unit | Mean recorded tokens per unit | Mean elapsed time |
| --- | ---: | ---: | ---: |
| Direct | 1.0 | 1.6k | 7 s |
| TA | 26.4 | 221.4k | 332 s |
| TA+CV | 52.1 | 288.1k | 467 s |

All 81 generation and 81 arm-blind judge units completed. All 27 TA+CV units recruited and invoked
Spatial-CV, produced a valid bundle, and exposed it to the final Hypothesis step. All 54 native
units recorded the native TissueAgent graph, dispatched every Manager step, met the planned step
count, and wrote a complete final artifact; no plan artifact mismatch, unexpected artifact, or
unassigned step was recorded. No semantic retry or fallback model was recorded, and no generation
unit was rerun. The per-paper and merged aggregates pass their hash audits.

Early local judge attempts logged rate-limit retry warnings and ran inside a sandbox without
network access. Ten failed judge attempts, covering the replicate-1 units of GraphST, STAGATE, and
SOTIP, ended in `APIConnectionError`. They are archived under `judging/.../failed/`, were retried with
`--retry-failed`, and are not scored.

## Twenty-paper combined

| Method | Mean paper hit fraction | Pooled hit fraction | Complete units |
| --- | ---: | ---: | ---: |
| Direct | 55.83% | 54.58% | 60/60 |
| TA | 55.37% | 54.23% | 60/60 |
| TA+CV | **66.16%** | **63.73%** | 60/60 |

| Contrast | Estimate | Paired 95% interval | Papers | Win / tie / loss |
| --- | ---: | ---: | ---: | ---: |
| TA - Direct | -0.46 points | [-4.69, +3.63] | 20 | 10 / 2 / 8 |
| TA+CV - TA | +10.80 points | [+3.35, +17.32] | 20 | 16 / 2 / 2 |

| Method | Mean model calls per unit | Mean recorded tokens per unit | Mean elapsed time |
| --- | ---: | ---: | ---: |
| Direct | 1.0 | 1.8k | 7 s |
| TA | 27.0 | 237.7k | 291 s |
| TA+CV | 53.7 | 286.6k | 408 s |

All 60 TA+CV units recruited, invoked, and exposed a valid Spatial-CV bundle.

## Historical eleven-paper result

### Main comparison

All eleven papers are complete. The main comparison requested here is Direct, native TissueAgent
(TA), and TissueAgent with the modified Spatial-CV agent recruited for proposal drafting (TA+CV).

| Method | Mean paper hit fraction | Pooled hit fraction | Complete units |
| --- | ---: | ---: | ---: |
| Direct | 46.21% | 45.54% | 33/33 |
| TA | 47.24% | 46.43% | 33/33 |
| TA+CV | **55.08%** | **52.38%** | 33/33 |

The primary paired paper contrasts used 10,000 bootstrap samples after averaging the three
replicates within each paper.

| Contrast | Estimate | Paired 95% interval | Papers |
| --- | ---: | ---: | ---: |
| TA - Direct | +1.03 points | [-2.92, +4.90] | 11 |
| TA+CV - TA | +7.84 points | [-3.09, +17.64] | 11 |

TA+CV beat TA on nine papers, tied on one, and lost on one. The eleven-paper intervals include
zero, so this is evidence of an integration signal rather than a statistically established
superiority claim.

### Paper-level results

Values are mean candidate hit fractions across three replicates.

| Paper | Direct | TA | TA+CV |
| --- | ---: | ---: | ---: |
| SpaCET | 30.56% | 36.11% | **38.89%** |
| Kidney cell-state atlas | 53.33% | 60.00% | **100.00%** |
| spEMO | 27.27% | 30.30% | **36.36%** |
| Kasumi | 25.93% | 22.22% | **37.04%** |
| Spotiphy | 51.52% | **63.64%** | 27.27% |
| ovrlpy | 62.96% | 51.85% | **70.37%** |
| Renoir | 59.26% | **66.67%** | **66.67%** |
| INSPIRE | 55.56% | 50.00% | **66.67%** |
| NeST | 60.61% | 63.64% | **78.79%** |
| STORIES | **42.42%** | 36.36% | 39.39% |
| RESCUE | 38.89% | 38.89% | **44.44%** |

### Cost and integrity

| Method | Mean model calls per unit | Mean recorded tokens per unit | Mean elapsed time |
| --- | ---: | ---: | ---: |
| Direct | 1.0 | 1.9k | 7 s |
| TA | 27.5 | 251.1k | 257 s |
| TA+CV | 54.9 | 285.3k | 361 s |

All 99 generation and 99 arm-blind judge units completed. All 33 TA+CV units recruited and
invoked Spatial-CV, produced a valid 3N-call bundle, and exposed it to the final Hypothesis step.
All 66 native units traversed Planner, Recruiter, Manager, Evaluator, and Reporter. No semantic
retry or fallback model was recorded. The retained aggregate passes its hash audit.

Two non-scoring bookkeeping irregularities were retained rather than selectively rerun. One TA
plan duplicated `hypotheses/` in an expected-artifact string while writing the real artifact to
the correct path. One TA+CV PlanStore snapshot remained stale even though the three Manager
steps and audited artifacts were complete. Neither changed the generated proposals or violated
the integration gates.

## Reproducibility

- [Twenty-paper combined aggregate](../benchmark/spatial_cellbench/results/combined_20paper_aggregate.json)
- [Nine-paper extension aggregate and checkpoints](../benchmark/spatial_cellbench/results/formal_9paper_extension/)
- [Nine-paper provenance, commands, and verification](../benchmark/spatial_cellbench/results/formal_9paper_extension/PROVENANCE.md)
- [Eleven-paper formal aggregate](../benchmark/spatial_cellbench/results/formal_aggregate.json)
- [Frozen analysis specification](../benchmark/spatial_cellbench/analysis_spec.md)
- [Corpus manifest](../benchmark/spatial_cellbench/data/corpus_manifest.json)
- [Benchmark implementation](../benchmark/spatial_cellbench/run.py)

Candidate-generating workers used `o3-mini` with medium reasoning. Native outer orchestration
used `gpt-5.1` with high reasoning, and the arm-blind judge used `gpt-4o`. Each batch is frozen
under its own source fingerprint:

| Batch | Papers | Source fingerprint | Code |
| --- | ---: | --- | --- |
| Eight-paper | 8 | `807543813308368098e302c4faed12578ef62853faea947ead00e58b59786484` | recorded in the eleven-paper aggregate |
| Three-paper extension | 3 | `1811206f1a7dd2c8fae7b95c60609b4b0cda86219d674b245714079ff2542fe0` | `e56aa78` |
| Nine-paper extension | 9 | `4e6f997fb26d818935a9e2cc2900bcbbca997b92f766cbe663d9915c6f509c5a` | `4716b53` |

The combined and eleven-paper aggregates record every batch and its checkpoint hash in
`source_batches`.
