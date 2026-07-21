# Spatial CellBench formal results

_Eleven spatial papers, three replicates per method, completed 2026-07-21._

## Main comparison

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
| NeST | 60.61% | 63.64% | **78.79%** |
| STORIES | **42.42%** | 36.36% | 39.39% |
| RESCUE | 38.89% | 38.89% | **44.44%** |

## Cost and integrity

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

- [Formal aggregate](../benchmark/spatial_cellbench/results/formal_aggregate.json)
- [Frozen analysis specification](../benchmark/spatial_cellbench/analysis_spec.md)
- [Corpus manifest](../benchmark/spatial_cellbench/data/corpus_manifest.json)
- [Benchmark implementation](../benchmark/spatial_cellbench/run.py)

Candidate-generating workers used `o3-mini` with medium reasoning. Native outer orchestration
used `gpt-5.1` with high reasoning, and the arm-blind judge used `gpt-4o`. The first eight papers
use source fingerprint `807543813308368098e302c4faed12578ef62853faea947ead00e58b59786484`;
the three-paper extension uses `1811206f1a7dd2c8fae7b95c60609b4b0cda86219d674b245714079ff2542fe0`
from commit `e56aa78`. The formal aggregate records both frozen batches and their checkpoint hashes.
