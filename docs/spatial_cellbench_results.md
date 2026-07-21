# Spatial CellBench formal results

_Eight spatial papers, three replicates per method, completed 2026-07-21._

## Main comparison

All eight papers are complete. The main comparison requested here is Direct, native TissueAgent
(TA), and TissueAgent with the modified Spatial-CV agent recruited for proposal drafting (TA+CV).

| Method | Mean paper hit fraction | Pooled hit fraction | Complete units |
| --- | ---: | ---: | ---: |
| Direct | 45.80% | 44.87% | 24/24 |
| TA | 47.60% | 46.58% | 24/24 |
| TA+CV | **55.41%** | **51.71%** | 24/24 |

The primary paired paper contrasts used 10,000 bootstrap samples after averaging the three
replicates within each paper.

| Contrast | Estimate | Paired 95% interval | Papers |
| --- | ---: | ---: | ---: |
| TA - Direct | +1.80 points | [-3.47, +6.72] | 8 |
| TA+CV - TA | +7.81 points | [-7.49, +20.76] | 8 |

TA+CV beat TA on six papers, tied on one, and lost on one. The eight-paper intervals include
zero, so this is evidence of an integration signal rather than a statistically established
superiority claim.

## Paper-level results

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

## Cost and integrity

| Method | Mean model calls per unit | Mean recorded tokens per unit | Mean elapsed time |
| --- | ---: | ---: | ---: |
| Direct | 1.0 | 1.9k | 7 s |
| TA | 28.2 | 260.2k | 258 s |
| TA+CV | 53.7 | 280.2k | 341 s |

All retained 72 generation and 72 arm-blind judge units completed. All 24 TA+CV units recruited and
invoked Spatial-CV, produced a valid 3N-call bundle, and exposed it to the final Hypothesis step.
All 48 native units traversed Planner, Recruiter, Manager, Evaluator, and Reporter. No semantic
retry or fallback model was recorded. The retained aggregate passes its hash audit.

Two non-scoring bookkeeping irregularities were retained rather than selectively rerun. One TA
plan duplicated `hypotheses/` in an expected-artifact string while writing the real artifact to
the correct path. One TA+CV PlanStore snapshot remained stale even though the three Manager
steps and audited artifacts were complete. Neither changed the generated proposals or violated
the integration gates.

## Reproducibility

- [Formal aggregate](../benchmark/spatial_cellbench/results/formal_aggregate.json)
- [Frozen analysis specification](../benchmark/spatial_cellbench/analysis_spec.md)
- [Corpus manifest](../benchmark/spatial_cellbench/data/corpus_manifest.json)
- [Benchmark implementation](../benchmark/spatial_cellbench/run.py)

Candidate-generating workers used `o3-mini` with medium reasoning. Native outer orchestration
used `gpt-5.1` with high reasoning, and the arm-blind judge used `gpt-4o`. This historical run's
source fingerprint is `807543813308368098e302c4faed12578ef62853faea947ead00e58b59786484`.
The current eleven-paper corpus intentionally has a new fingerprint, so its future checkpoints
must not be merged with this aggregate.
