# Matched-task cell-annotation comparison

Completed 2026-09-06 using GPT-5.1 for the new Biomni and SpatialAgent evaluations.

[Comparison PNG](evaluation_comparison.png) · [Comparison PDF](evaluation_comparison.pdf) ·
[All-method scores](comparison_metrics.tsv) · [Individual runs](individual_run_metrics.tsv) ·
[Full provenance](provenance.json)

## Redraw from a clone

After installing the TissueAgent environment with `uv sync`, run from the repository root:

```bash
uv run --no-sync python -m demo.cell_annotation.plot_agent_baseline_comparison \
  --results-dir demo/outputs/cell_annotation/agent-baselines-matched-heart-bcl-stereoseq-gpt51-20260906 \
  --output-dir demo/outputs/cell_annotation/local-comparison-replot
```

This needs only the two committed metric tables and NumPy/pandas/Matplotlib, not API keys, raw
data, or Biomni/SpatialAgent environments. Choose a new output directory. Redrawing does not
recompute metrics or repeat source-file validation. Paths inside `provenance.json` identify
original archived artifacts; those large data and run directories are not included in this
bundle. See the [setup and evaluation guide](../../../../docs/cell_annotation_agent_baselines.md)
for the distinction between plotting, new evaluations, and a full provenance audit.

## What was matched

Both new baselines received byte-identical copies of the original selection-blind AnnData files
used by the saved TissueAgent runs. The scientific task was recovered from those saved prompts,
verified across all three TissueAgent replicates per dataset, and changed only at input/output
paths. BCL's study context and cell-identity/disease-state scope were retained verbatim.
Required execution instructions were appended separately; these are not identical full prompts.

Biomni's adapter no longer normalizes, selects PCA components, builds neighbors or creates Leiden
clusters. The actual Biomni A1 agent decides and executes preprocessing and annotation. SpatialAgent
executes its native Spatial Annotation tools. All LLM-based comparison methods use the GPT-5.1
model ID; CellTypist is not LLM-based.

Scoring uses the same frozen truth, label contracts, mappings and exclusions as the existing
comparison. BCL has 49,910 input cells and 49,566 scored cells after excluding 344 B14 cells.
Heart has 228,635 cells. Mouse has 478,740 cells in the frozen 15-section Stereo-seq panel;
its truth is publisher-provided Spatial-ID annotation, compared in shared Cell Ontology space,
not manual ground truth.

## New results

All values below are percentages. The accompanying figure includes the latest validated
TissueAgent, GPTCellType and CellTypist results as well.

| Dataset | Biomni accuracy | Biomni macro F1 | SpatialAgent accuracy | SpatialAgent macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Developing human heart | 0.0† | 0.0† | 90.5 | 42.8 |
| BCL | 47.5 | 53.4 | 21.9 | 32.7 |
| Mouse brain Stereo-seq | 12.2 | 3.9 | 46.7 | 6.3 |

† Biomni returned the generic label `cell` for every heart observation. Its generated code
mistook an unnamed gene-index header for missing identifiers, despite valid gene symbols in
the original `var_names`. This completed output is retained, mapped to Unassigned and explicitly
flagged as an annotation failure; it was not replaced based on performance. The run's
`annotation_outcome.json` records the input check and transcript evidence.

For BCL, Biomni chose its own preprocessing and clustering, then used its native single-cell
marker annotation tool. For mouse, it chose preprocessing, Leiden clustering and marker ranking,
then generated its own marker-rule annotation code; its output had seven distinct labels.

SpatialAgent's mouse attempt initially guessed `celltype_transferred_1.csv`, although the native
transfer tool wrote `celltype_transferred.csv`. A continuation used verified copies of its own
preprocessing, reference and transfer artifacts, with the correct tool filenames stated explicitly.
No final predictions existed in the failed attempt. Clustering was not saved before the error,
so native automatic-resolution clustering was repeated; the continuation selected resolution 1.0
and 19 clusters. Its final labels were only `Neuron` and `Glial cell`, without manual refinement.

## Label mapping and interpretation

GPT-5.1 label mapping is an existing evaluator-side choice, not a Biomni or SpatialAgent
requirement. Known labels use existing aliases; only unfamiliar free-text label names and
allowed target definitions are sent to the mapper. It does not receive per-cell truth, expression
or performance, and it must not infer disease or subtype information absent from a raw label.
Changing this policy would require consistent rescoring of all comparators.

This comparison matches input, scientific task and model ID, not native system prompts,
resources, preprocessing choices or computational budgets. TissueAgent is shown as mean ± sample
SD across three runs; each other method has one completed evaluation per dataset. Initial
incomplete attempts and execution recoveries are preserved, not selected by score. The Biomni
environment needed a project-local Leiden dependency overlay; its original Conda environment
was not changed.

## Validation

The comparison validates original query hashes, saved scientific prompts, model selections,
evaluation lineage, prediction/mapping hashes, configured reference-source exclusions and
reference/query observation-ID overlap. All six new outputs cover every input observation;
coverage after semantic label mapping can be lower. The provenance records six new evaluations
and five failed/interrupted attempts; the tables contain 15 summaries and 21 individual runs.
The plot was visually checked. Final targeted tests: 81 passed, plus six subtests; scoped Ruff
checks passed.
