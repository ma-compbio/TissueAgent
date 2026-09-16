# Tissue-niche annotation: TissueAgent, Biomni and SpatialAgent

The named-annotation benchmark has its own preparation, adapters, worker, evaluator and plotting
modules in `demo/tissue_niche/`. It does not import the cell-annotation scripts. LLMiniST/SPEAK is
deferred. The older BANKSY/scNiche clustering comparison remains separate.

## Input and annotation contract

Each method receives an identical H5AD for each physical section containing only:

- Expression in `X` and gene identifiers in `var_names`.
- Supplied cell types in `obs['cell_type']`.
- Two-dimensional coordinates in `obsm['spatial']`.
- Opaque cell IDs in `obs_names`.

All other observation/gene columns, layers, raw data, embeddings, graphs and unstructured metadata
are removed. The separate public contract supplies species, tissue/assay context, expression state,
coordinate units and the final allowed tissue labels. All three methods receive the same task
prompt, with only runtime paths substituted. It describes the dataset and available data in
ordinary language, asks for the anatomical tissue region containing each cell, lists the allowed
labels, permits `Unmatched`, and specifies the output H5AD path and `obs['tissue_niche']`.
The prompt names `obs['cell_type']`, `obsm['spatial']`, and the output annotation column.
Expression state, disease context and known spatial units are stated as dataset facts, without
prescribing the analysis.

New studies use prompt version `natural_keys_v4`; the earlier `natural_v3` remains evaluable. There is no execution appendix: the task prompt
does not prescribe tools, skills, inspection order, clustering, preprocessing, plots, reporting,
model settings or benchmark access rules. Native agent system prompts, tools and skills remain
part of each method. A native agent may still choose to generate plots or a report.

The complete [heart prompt](../demo/tissue_niche/prompt_examples/developing_human_heart.txt)
and [OVCA prompt](../demo/tissue_niche/prompt_examples/ovca_xenium_spatialfusion.txt) are available
under `demo/tissue_niche/prompt_examples/`. These examples are generated from the public dataset
manifests by [the prompt builder](../demo/tissue_niche/protocol.py), which is the source used by
the runner. The examples use TissueAgent project paths; runtime paths are substituted per method.

Model configuration, stripped inputs, input-hash checks, returned cell-type checks and cell-ID
alignment are handled by the runner. Missing predictions remain in the evaluation cohort as
`Unmatched`. These checks do not restrict filesystem or network access; see the isolation limits
below. The requested `obs['tissue_niche']` output field is an output contract, not an analysis recipe.

The final September 13 comparison matches the latest TissueAgent model configuration with
`reasoning_effort: high`. The SDK binding applies this setting to chat and Responses calls,
removes an explicit temperature, and logs the effective settings. Chat calls receive the
repetition seed; Responses has no seed argument. Biomni still runs through native `A1.go`,
with its stream configuration bound to the shared graph limit rather than its hard-coded 500.
SpatialAgent retains its default automatic figure review, and both `slide_key` and
`anatomical_path` schemas accept the native `None` defaults. Native tool and skill choices
remain autonomous. The retained Biomni environment's missing `leidenalg==0.10.2` is supplied
through a local `BIOMNI_PYTHONPATH` dependency overlay.

Baseline collection now uses the same canonical/unambiguous annotation selection as TissueAgent.
Valid saved annotations survive a later native workflow error as partial runs. Export failures
retain the native messages and error details. No failed attempt is replaced using its score.
`demo.tissue_niche.final_agent_evaluation` audits a frozen TissueAgent study, runs the two
baselines, and composes a comparison referencing the original immutable records. It rejects
different prompts, input/truth cohorts, models, budgets, seeds, and missing or duplicate attempts.

Native methods may edit their private working copies during analysis. The runner records the
post-run working-copy hash and validates final cell IDs, supplied cell types and coordinates
against the immutable canonical query, whose hash must remain unchanged. This avoids rejecting
derived batch metadata in a baseline while overlooking equivalent edits to TissueAgent's extra
uploaded copy. For archived runs rejected solely by the former working-copy hash rule,
`--collection-decision <json>` creates derived collection records with the original attempts and
decision hashes preserved; it performs no new inference or label changes. The same annotation
checks apply to all retained methods.

The September 8 heart/OVCA runs used the earlier guided prompt. Their saved prompts, predictions
and scores remain unchanged and evaluable as `guided_v1`; unversioned archives use that historical
template. The intermediate structured `task_only_v2` prompt also remains supported for evaluation.
New prompts require a fresh study ID, and a comparison cannot mix prompt versions.

Preparation retains the original cell IDs, section identities and ground truth in a private table.
Workers receive only the public query and task contract. Section-level execution avoids requiring
sample/batch metadata in the shared input. All sections and all cells remain in the evaluation cohort.

`agent_manifests/developing_human_heart.yaml` describes the existing heart MERFISH source and held-out
truth: 228,635 cells, 238 genes, three sections and eight tissue labels. Its expression is already
log-transformed. `agent_manifests/ovca_xenium_spatialfusion.yaml` describes the Xenium OVCA source:
338,695 cells and 5,101 genes in one section, `major_celltype`, `spatial` in microns, and held-out
`path_region`. The source's `region` column is constant (`cell_circles`), not a tissue label.
OVCA's target classes are Tumor, Smooth muscle, Necrosis, Fallopian tube and Ovary. Truth Unassigned
and null are excluded from metrics, while those cells remain in the input for spatial context.
The verified source has 246,544 scored cells and 92,151 Unassigned cells.
The verified Zenodo archive names its ovarian member `benchmark_processed_data/processed_OVCA.h5ad`
(rather than `preprocessed_OVCA.h5ad`); the downloader uses that exact member.

The agents run in fresh working directories with fresh data/resource directories. **Process isolation
is not an operating-system filesystem sandbox.** The worker does not receive private data paths,
but its Python/code tools retain the host process's access rights and network access. For a study
requiring enforced access isolation, execute on an isolated host/container with only the public query,
required runtime code and credentials available; copy predictions to the evaluator afterward. The
run record explicitly reports this limitation. Do not describe these workers as an OS security boundary.

## Method behavior and model selection

The default model is `gpt-5.1`. Set a global `--model`, edit the study configuration, or specify a
method-level `model` override in that configuration. Results include the selected model so different
model conditions remain identifiable. The native method/provider must support the selected model.

- **Biomni:** launches native `A1` and lets the agent select and execute the tissue annotation analysis.
  No adapter-created clustering or TissueAgent labeler is supplied. Its data lake starts empty; the
  constructor is configured to avoid downloading bundled benchmark/reference data. Factory bindings
  propagate the selected model/source to native calls.
- **SpatialAgent:** launches the full native agent with its tissue-niche tools available. A narrow
  binding passes the shared context and target vocabulary through the native `data_info` argument,
  uses the supplied cell types and sets `anatomical_path=None`. The native marker/composition/spatial
  summaries and image-plus-LLM annotation are retained. Multiple clusters can share one label. Text
  response blocks are normalized for the upstream parser without changing label semantics.
  A process-local compatibility binding also supplies its legacy `cm.get_cmap` call through
  `pyplot.get_cmap` when the installed Matplotlib has removed that API.
  Its generated tool schema is corrected to accept an explicit `anatomical_path=None`, matching
  the native function's default; the upstream non-nullable string annotation otherwise rejects it.
- **TissueAgent:** runs the full graph from a staged source/knowledge copy with a fresh workspace,
  avoiding changes to the user's active project. It receives the shared task and chooses its own
  workflow through its native planning, tool and skill machinery. Model selection applies to
  orchestration and worker roles. The worker binds the shared public context, field names, label
  vocabulary, and output path through native task context. The active Markdown plan guides the
  specialist to inspect fields and candidate spatial scales, choose its configuration, and annotate.
  A clustering-only preview returns granularity and spatial/composition evidence before labeling;
  the agent may preview one justified alternative and labels only the selected candidate. Its
  selected radius is retained in candidate metadata for consistent downstream evidence.
  Native labeling receives public biological context, cluster extent and connectivity, neighboring
  cell-type composition, and an overview of the other clusters. Existing clusters can be labeled
  without rerunning UTAG, including after an agent-justified spatial subdivision.
  The native writer validates cell IDs and labels in a real H5AD at the requested path. Initial
  labels are retained in an additional column when an existing annotation is refined once.
  Collection accepts the canonical H5AD or one unambiguous native annotation H5AD. Textual aliases
  with `.h5ad` filenames are recorded and skipped; they cannot replace the actual annotation data.
  An alias may designate one native H5AD explicitly when multiple revisions exist; otherwise
  ambiguous revisions are rejected. Selection never uses annotation accuracy. A workflow error
  after a valid annotation was saved is recorded as a partial run, preserving those predictions
  and the error separately. An error before any valid output remains a failed run.
  Completed native artifacts are hard-linked into archives on the same filesystem to avoid
  duplicating expression matrices. Cross-filesystem archives are copied.

OpenAI chat/Responses calls inside each worker are bound to the selected model and logged, including
the response model when the SDK returns it. Native factory constructions are also logged for the
external agents. Code launched in a separate interpreter does not inherit Python model bindings.
The task prompt does not instruct agents to stay in-process; model enforcement and auditing cover
the bound process, not arbitrary subprocesses or direct HTTP requests. Python/NumPy are seeded;
upstream defaults, remote APIs and other runtimes may remain nondeterministic. Repetitions are
independent runs, not a guarantee of deterministic LLM sampling.

## Environments

Use TissueAgent's normal environment plus separate native environments for the baselines:

The headless TissueAgent runner starts a local Jupyter gateway for its coding tools. Install it in
the TissueAgent environment if it is not already present:

```bash
uv pip install --python .venv/bin/python jupyter-kernel-gateway==3.0.1
```

- Biomni `0.0.8`, previously integrated at upstream revision
  `400c1f366b96a35ca253e13c9b06c5076af41d65`.
- SpatialAgent revision `e51ec0f6b1e5c8ddbc52dae846031fbc04d3c9d6`; the runner checks the checkout
  revision and requires its package source to be unchanged.

Follow [Biomni's setup](https://github.com/snap-stanford/biomni) and
[SpatialAgent's setup](https://github.com/Genentech/SpatialAgent), including scientific dependencies
needed by their native workflows. Do not install their dependency sets into TissueAgent's environment.

```bash
export BIOMNI_PYTHON=/absolute/path/to/biomni/bin/python
export SPATIALAGENT_PYTHON=/absolute/path/to/spatialagent/bin/python
export SPATIALAGENT_REPO=/absolute/path/to/SpatialAgent
export OPENAI_API_KEY=...
```

The optional `BIOMNI_PYTHONPATH` or `SPATIALAGENT_PYTHONPATH` variables provide an explicit dependency
overlay when needed; the generic parent `PYTHONPATH` is not inherited. Interpreter/source paths can
also be configured per method using `python_executable` and `source_path`. Biomni provider selection
uses `biomni.source`; SpatialAgent's Azure routing uses `spatialagent.use_azure`.

The checked-in [study configuration](../demo/tissue_niche/configs/agent_comparison.yaml) selects both
datasets, all three methods, GPT-5.1, and requested seeds 42, 43, 44. Temporary runtime files default
to `/scratch/tissue_niche_agents`; use `--runtime-root` for another writable execution directory.
Runtime directories are retained for debugging and named in run records.
Set a method's `seeds` list to override the study-wide repetitions (for example, three TissueAgent
seeds and `seeds: [42]` for each baseline). `max_workers` controls concurrent section jobs and defaults
to one. Each TissueAgent worker starts its own local Jupyter gateway on a separate port.

## Prepare, run and evaluate

Run from the repository root. These commands are separate: preparation and dependency preflight
make no model requests. `run` executes the agents and incurs normal provider usage.

```bash
# Download the requested archive, verify MD5, and extract only processed_OVCA.h5ad.
uv run --no-sync python -m demo.tissue_niche.spatialfusion_ovca download

# Build strict inputs for both datasets. Add --dataset developing_human_heart for heart only.
uv run --no-sync python -m demo.tissue_niche.run_agents prepare
uv run --no-sync python -m demo.tissue_niche.run_agents preflight

# Fresh study: all three methods, both datasets, all configured repetitions.
uv run --no-sync python -m demo.tissue_niche.run_agents run \
  --study-id tissue-niche-agents-gpt51-v3

# Or run just the two new baselines on heart in a separate study.
uv run --no-sync python -m demo.tissue_niche.run_agents run \
  --dataset developing_human_heart --method biomni --method spatialagent \
  --model gpt-5.1 --seed 42 --study-id heart-agent-baselines-v3
```

Acquisition uses bounded HTTP range requests because the full archive may exceed gateway timeouts.
Interrupted downloads resume from the assembled prefix and the complete archive is checked
against the published MD5 before extraction. The H5AD gets a separate SHA256 acquisition record.

Studies live under `demo/outputs/tissue_niche/agent_comparisons/<study-id>/`. Each dataset, method,
seed and section has a run record, full prompts, native artifacts, logs, raw labels and canonical
per-cell predictions. Input, prediction and worker/source provenance is retained. Run directories
are immutable. `--resume` with the same configuration skips finalized attempts, including failures,
and runs jobs not yet attempted. It does not replace poor/failed results with favorable reruns.
Use a new study ID for changed prompts, configuration or a deliberately new attempt. A process
interruption leaving an unindexed run directory requires inspection before resuming that study.

```bash
uv run --no-sync python -m demo.tissue_niche.evaluate_agents \
  --study-dir demo/outputs/tissue_niche/agent_comparisons/tissue-niche-agents-gpt51-v3

uv run --no-sync python -m demo.tissue_niche.plot_agent_comparison \
  --study-dir demo/outputs/tissue_niche/agent_comparisons/tissue-niche-agents-gpt51-v3
```

Evaluation writes `evaluation/metrics.tsv`, `summary.tsv`, per-section and per-class reports, and
confusion matrices. Macro F1 averages the declared biological classes. Balanced accuracy is their
mean recall over truth-supported classes. Dataset-level scores pool cells across sections first.
Whitespace/case normalization is allowed; unknown or missing predictions become `Unmatched` and
count as errors on labeled cells. There is no evaluator-side LLM mapping or ground-truth-based
cluster matching. Duplicate/foreign IDs, altered artifacts and mismatched inputs are rejected.

Partial runs retain the full denominator; unavailable sections count as `Unmatched` when another
section has usable output. Entirely failed runs have no score. Tables and bars show completeness;
averages include usable partial runs. Archived scores from older input protocols are not imported
as matched TissueAgent results.

Figures include per-section truth/method spatial maps with one fixed palette and per-dataset metric
bars with individual run dots and mean ± SD. Spatial plots default to the first configured seed;
use `--seed` to plot another repetition. `--performance-only` redraws bars using saved evaluation
tables without expression, coordinates, API keys or baseline environments.
When a baseline has only one configured seed, its spatial panel is reused alongside each selected
TissueAgent seed and explicitly labeled with its own seed. It still counts as one run in metrics.

The [agent demo notebook](../demo/tissue_niche_agent_baselines.ipynb) calls these same functions.

## Validation

```bash
.venv/bin/python -m pytest tests/test_tissue_niche_agent_comparison.py -q

# Optional: real SpatialAgent summaries/plotting/parsing with a controlled LLM response.
# Requires the SPATIALAGENT_* environment variables above; makes no LLM API call.
.venv/bin/python -m pytest tests/test_tissue_niche_spatialagent_native.py -q
```

These tests establish input integrity, adapter behavior, metrics and plotting. They do not establish
biological accuracy or successful autonomous full-cohort execution; those require actual study runs.

## Comparing TissueAgent revisions

Keep each revision in a fresh study directory. The comparator verifies frozen run records and
input identities and evaluates every cell, counting missing sections as Unmatched:

```bash
python -m demo.tissue_niche.compare_tissueagent_revisions \
  --study Old=path/to/archived-study \
  --study Revised=path/to/new-study \
  --output-dir demo/outputs/tissue_niche/revision-comparison
```

It writes pooled and per-section metrics, per-class results, an execution inventory, spatial
plots, per-seed performance bars, and mean ± sample-SD bars with individual repetition dots.
The labels distinguish repetitions from section-workflow completion; summary tables also count
sections with saved predictions. Review all attempted
revisions and use a further seed to check the final revision. Changes informed by these development
results require confirmation on untouched data; do not select graph parameters or label mappings
using held-out annotations.

An optional study configuration `storage_budget: {root: /path/to/new/experiment,
max_bytes: 28000000000}` monitors allocated bytes during workers. Use an experiment-specific root
containing every new runtime, leave room for final figures, and retain old studies unchanged.
