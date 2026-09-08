# Biomni and SpatialAgent cell-annotation baselines

This comparison covers developing human heart, B-cell lymphoma (BCL), and Han mouse brain
Stereo-seq. TissueAgent is compared with GPTCellType, CellTypist, Biomni, and SpatialAgent.

## Review and redraw the saved results

The committed [results bundle](../demo/outputs/cell_annotation/agent-baselines-matched-heart-bcl-stereoseq-gpt51-20260906/README.md)
contains the final PNG/PDF, summary and individual-run metric tables, and provenance. From the
repository root, redraw the figure into a new directory with:

```bash
uv run --no-sync python -m demo.cell_annotation.plot_agent_baseline_comparison \
  --results-dir demo/outputs/cell_annotation/agent-baselines-matched-heart-bcl-stereoseq-gpt51-20260906 \
  --output-dir demo/outputs/cell_annotation/local-comparison-replot
```

Run `uv sync` first if the TissueAgent environment has not been installed. Redrawing needs only
NumPy, pandas, and Matplotlib; it does not require API keys, either upstream agent environment,
or expression data. Choose a new output directory; existing directories are never overwritten.
This mode renders saved scores and does not repeat the source-run audit or evaluation.

Large query/reference H5AD files, per-cell predictions, upstream checkouts, environments, caches,
and historical run directories are intentionally not committed. The provenance retains their
original paths and hashes as an audit record, not portable download links. Re-evaluating or
running the full source audit requires those archived artifacts. In particular, the matched-task
driver expects the saved TissueAgent study manifest named by its `STUDY` constant, its referenced
prepared runs and transcripts, and their query, truth, and mapping files. The full plotting audit
also needs the earlier baseline provenance and source files named by `BASELINES`, plus CZI
reference metadata. These are not needed to redraw the committed figure.

## Prepare inputs for a new evaluation

The three manifests are in `demo/cell_annotation/manifests/`, with frozen label contracts in
`demo/cell_annotation/mappings/`. Source locations, hashes, and reference requirements are recorded
in each manifest. Developing human heart uses its existing prepared source. BCL and Han Stereo-seq
have preparation commands (run `--help` before downloading or building large inputs):

```bash
uv run python -m demo.cell_annotation.bcl --help
uv run python -m demo.cell_annotation.han_mouse_brain_stereoseq --help
```

`demo/cell_annotation_benchmark.ipynb` is an interactive quick/full demo for these three datasets,
not a replay of the archived matched-task study. Its direct smoke-test scoring does not apply the
study's post-hoc name mapping, BCL exclusions, or mouse shared-ontology scoring. For the published
comparison protocol, use the matched-task driver with the archived inputs described below.

## Baseline entry points

The cell-annotation benchmark exposes both upstream agents through the same entry point and output
contract as CellTypist and GPTCellType:

```python
from demo.cell_annotation.baselines import run_biomni, run_spatialagent

biomni_result = run_biomni(prepared, model="gpt-5.1")
spatialagent_result = run_spatialagent(prepared, model="gpt-5.1")
```

Each runner reads the selection-blind `query.h5ad`, invokes the upstream agent, and writes
`<method>_predictions.tsv` in the benchmark run directory. `evaluate_predictions(prepared)` then
discovers and scores those files exactly as it does the existing baselines. Agent transcripts,
stdout/stderr, the annotated H5AD, the selected model, and upstream version/revision are retained
under the method's run directory.

## Isolated upstream environments

Do not install either agent into TissueAgent's environment. SpatialAgent recommends Python 3.11
and LangGraph 1.x, while TissueAgent uses Python 3.12 and LangGraph 0.3. The runners launch each
agent with a separately configured Python executable so one notebook can still prepare and score
all methods.

Follow the upstream setup instructions. The adapters were implemented against these source
snapshots; the manifests enforce Biomni's package version and SpatialAgent's git revision:

- [Biomni setup](https://github.com/snap-stanford/biomni) at commit
  `400c1f366b96a35ca253e13c9b06c5076af41d65` (`biomni==0.0.8`). Its repository documents the
  full `biomni_env/setup.sh` environment and reduced alternatives. Install the checked-out Biomni
  package in that environment after creating it. The annotation adapter downloads only Biomni's
  required CZI cell-type index into `data/cache/biomni`; it does not fetch the unrelated full
  data lake. Biomni receives the original selection-blind query without adapter normalization,
  PCA, neighbors or clustering. The agent chooses its preprocessing and annotation workflow;
  the adapter does not force the native marker annotator or override its input/cluster arguments.
  It normalizes Responses API text blocks before the
  native per-cluster parser so current GPT-5 models satisfy Biomni 0.0.8's string-response contract.
- [SpatialAgent setup](https://github.com/Genentech/SpatialAgent) at commit
  `e51ec0f6b1e5c8ddbc52dae846031fbc04d3c9d6`. Run its `setup_env.sh` as documented by the
  project.

Before launching the TissueAgent notebook, export absolute paths to the resulting interpreters and
SpatialAgent checkout:

```bash
export BIOMNI_PYTHON=/absolute/path/to/biomni_e1/bin/python
export SPATIALAGENT_PYTHON=/absolute/path/to/spatial_agent/bin/python
export SPATIALAGENT_REPO=/absolute/path/to/SpatialAgent
export OPENAI_API_KEY=...
```

The Python paths can also be supplied directly with `python_executable=...`; SpatialAgent's source
checkout can be supplied with `source_path=...`.

The installed Biomni environment must support the preprocessing APIs the agent selects. The
fixed upstream environment includes `igraph` but may lack Scanpy's default `leidenalg` backend.
For the matched-task reruns, `leidenalg==0.10.2` was installed with `pip --target` into
`data/cache/biomni/python-dependencies` (compatible with the installed `igraph==0.11.9`). Biomni
jobs set `PYTHONPATH` to that absolute directory; the existing Conda environment is unchanged.
This adds an execution dependency, not adapter-created clustering. Dependency versions and the
overlay path are recorded in the successful Biomni run metadata.

When using that project-local dependency overlay, launch Biomni with it explicitly:

```bash
PYTHONPATH=/home/etrop/TissueAgent/data/cache/biomni/python-dependencies \
  .venv/bin/python -m demo.cell_annotation.run_agent_baseline_comparison \
  --method biomni --run-id my-matched-rerun
```

Choose an unused run ID so earlier attempts and their provenance remain intact.

## Changing the base model

The default for each LLM-backed baseline lives in the dataset manifest:

```yaml
baselines:
  gptcelltype:
    model: gpt-5.1
  biomni:
    model: gpt-5.1
    source: OpenAI
  spatialagent:
    model: gpt-5.1
    use_azure: false
```

For one comparison run, pass `model="..."` to the corresponding runner or change
`BASELINE_MODELS` in `demo/cell_annotation_benchmark.ipynb`. Biomni's global configuration, main
agent, and native single-cell annotation tool are all bound to that model. SpatialAgent receives the
model for its main agent, retrieval, subagents, and annotation calls; its separate default
web-search model is disabled for the benchmark. Its database-search tools use the upstream local
embedding option, avoiding a separate Azure embedding credential. The adapter redirects the
upstream repository-local embedding cache to `data/cache/spatialagent/embedding_cache` so the
pinned checkout can remain read-only. It also normalizes the Harmony result orientation across the
supported `harmonypy` versions; this is needed because `harmonypy 2.0` changed `Z_corr` from
components-by-cells to cells-by-components. The selected `use_azure` setting is bound to internal
model construction as well as the main agent, preventing subagents from silently reverting to the
upstream Azure default.

For a non-OpenAI Biomni model, also set `source=` and the provider's API key as described by
Biomni. For SpatialAgent, `use_azure: false` routes GPT models through the standard OpenAI API;
change it only when the selected upstream environment has the corresponding Azure configuration.

## Output contract

Both agents must produce an annotated H5AD with predictions in `.obs['cell_type']`. The adapter
checks that returned observation identifiers are unique and come from the selection-blind query,
then emits:

- `biomni_predictions.tsv` or `spatialagent_predictions.tsv`
- `biomni_predictions.run.json` or `spatialagent_predictions.run.json`
- `<method>/worker_request.json`, `worker_result.json`, `worker_stdout.log`, and
  `worker_stderr.log`
- `<method>/annotated.h5ad` for Biomni or `<method>/celltype_annotated.h5ad` for SpatialAgent

Upstream filtering is retained rather than hidden. If an agent returns fewer rows than the query,
the evaluator counts missing query cells as unassigned.

Full-cohort runs can set `agent_timeout_seconds` (Biomni) or `act_timeout_seconds` (SpatialAgent)
in the dataset manifest without changing annotation parameters. For an interrupted SpatialAgent
annotation step, `run_spatialagent(..., resume_from=previous_method_directory)` reuses completed
native preprocessing, reference files and Harmony label-transfer artifacts. It verifies identical
query bytes, model and upstream revision, copies and hashes the intermediates, and asks the agent
to finish native annotation; final annotations are never copied from the previous attempt.
SpatialAgent resume also requires an identical scientific task template. Autonomous Biomni runs
start fresh; the earlier adapter-prepared Leiden cache is deliberately not supported for this protocol.
Biomni's analysis runs in the existing Python process so the model bindings and response normalization
remain active. Child processes inherit the selected interpreter's `bin` directory first on `PATH`.

## Matched-task comparison reruns

`python -m demo.cell_annotation.run_agent_baseline_comparison --method biomni` (or
`--method spatialagent`) runs the three frozen cohorts used in the latest TissueAgent study.
It copies byte-identical query files and recovers the scientific task from the saved TissueAgent
prompts, verifying agreement across all three replicates. Only input/output paths are replaced.
This includes BCL's study context and its explicit cell-identity/disease-state annotation scope.
The recovered task and source hashes are saved in `task_prompt_alignment.json`.

The matched mouse SpatialAgent attempt stopped after guessing an indexed transfer CSV filename.
Its native tool had actually written `celltype_transferred.csv`. A continuation reuses its verified
preprocessing, reference and transfer files, with the correct tool input/output paths stated
explicitly; no final predictions existed in the failed attempt. Clustering was not saved before
the error, so the continuation repeats native automatic-resolution annotation. The failed attempt
and the hashes of reused files remain in the comparison provenance.

The adapters append execution/output requirements, model selection, and reference-leakage
exclusions; SpatialAgent is directed to its native Spatial Annotation workflow. Biomni is free
to choose its analysis. Neither adapter adds dataset titles or preset clusters. Native system
prompts, resources, preprocessing, and tool implementations still differ: this matches the input
and scientific task, not the methods' internal behavior or computational budgets.

The rerun driver allows six hours per execution block and twelve hours per worker, avoiding the
earlier short timeouts on the full mouse cohort. These limits can also be set through runner
arguments `execution_timeout_seconds` and `process_timeout_seconds`. The old evaluation artifacts
remain separate and describe the old adapter-preprocessed Biomni protocol.

Scoring retains the existing frozen label contract and GPT-5.1 name-mapping policy. Known labels
use existing mappings; only unfamiliar free-text names are mapped semantically into allowed target
labels. The mapper sees raw label strings and target definitions, not cell-level truth, expression
or performance. GPT-5.1 is an evaluator-side choice, not a requirement of Biomni or SpatialAgent;
changing it would require rescoring all comparison methods consistently.

A completed process is not necessarily a successful biological annotation. The matched heart
Biomni run incorrectly interpreted an unnamed index header as missing gene identifiers, despite
valid symbols in `var_names`, and returned only the generic label `cell`. Its completed output is
retained and scored as Unassigned, not replaced based on performance. `annotation_outcome.json`
records the input check and transcript evidence, and the comparison marks this annotation failure
explicitly. Any later input-format diagnostic must be reported separately from that primary run.
