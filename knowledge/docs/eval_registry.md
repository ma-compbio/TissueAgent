# Eval Registry — Design & Implementation Plan

## Context

Evaluation in TissueAgent today is split across two **disconnected** surfaces:

1. **Per-run, LLM-judged** — `evaluator_agent` reads artifacts (glob/grep/read) and emits
   `ROUTE: REPORT` or `ROUTE: REPLAN` (max 2 replans, `MAX_REPLANS`). Entirely prose-driven;
   no machine-checkable criteria.
2. **Plan-template "Evaluation Criteria"** — lines like `file_exists(lr_dotplot.png)` live in
   `knowledge/plans/*.md`, but **nothing parses or executes them** (verified: zero references to
   `file_exists` / "Evaluation Criteria" in `src/`). They are decorative.

There is no way to answer **"is the system getting better over time?"** across model/prompt
changes — no reusable metrics, no benchmark suite, no scorecard history.

This plan introduces an **`eval_registry`** providing (B) a reusable **metric registry** and
(C) an **offline benchmark suite** with a runner. It deliberately reuses three patterns already
in the repo: decorator-collected registries (like tools), markdown+frontmatter specs parsed by
`agents.agent_utils.parse_yaml_frontmatter` (like `plans/` and `skills/`), and session-driven
project isolation (`session.project_id` → `active_project_outputs()`).

Out of scope (can be layered later on top of the metric registry): reviving per-run `file_exists`
gates (option A) and standardized LLM-judge rubrics (option D).

## A run is fully determined by a *fixture*

A graph run (`session.agent.invoke({"messages": [HumanMessage(prompt)]}, config)` in
`server/routes/chat.py:_run_graph`) depends on exactly three things, all of which a benchmark
must pin:

1. **prompt** — the `HumanMessage`; this *is* the task. Phrasing changes planner routing
   (`ROUTE: DIRECT/CLARIFY/plan`), so it's a tested variable, not a label.
2. **inputs/datasets** — files staged in the active project (`uploads/`) or `library/`, referenced
   by path in the prompt. The agent sees only what's on disk.
3. **run_config** — `session.project_id` (isolation), `session.mode` (**must be `autopilot`** —
   copilot interrupts for human review and would block), `model` selection, `recursion_limit`.

The prompt + inputs + run_config together are the benchmark **fixture**.

## Layout

```
src/eval_registry/
  __init__.py
  metrics/
    __init__.py          # @metric decorator, REGISTRY, get_metric(), MetricSpec
    composition.py       # ari, f1_macro, abundance_jsd (reference_based)
    confidence.py        # mean_prediction_confidence, frac_low_confidence
    coverage.py          # n_shared_genes, n_cells, file_exists, csv_nonempty (artifact)
  benchmarks/
    spec.py              # load benchmark .md → BenchmarkSpec (frontmatter loader)
    fixture.py           # materialize fixture: temp project, stage inputs, set session
    tool_runner.py       # tier=tool: call tool fn directly with args+inputs
    pipeline_runner.py   # tier=pipeline: invoke real graph from prompt
    score.py             # resolve metrics from REGISTRY, compare to thresholds
    scorecard.py         # append-only results/benchmarks/scorecard.jsonl + diff
knowledge/benchmarks/    # markdown specs (one per benchmark), status: enabled
  manifest.yaml          # dataset URLs + sha256 checksums (data lives OUTSIDE git)
  visium_decon_lymphnode.md
  harmony_annotate_brain.md
scripts/
  fetch_benchmarks.py    # read manifest → download + checksum into cache, idempotent
results/benchmarks/      # scorecard.jsonl (gitignored), one row per (benchmark, run, commit)
workspace/library/benchmarks/   # local cache target for fetched datasets (gitignored)
```

## B. Metric registry (the linchpin)

Decorator-collected, like tool lists. One definition, referenced by name from tool benchmarks,
pipeline benchmarks, and (later) per-run gates.

```python
# src/eval_registry/metrics/__init__.py
@dataclass
class MetricSpec:
    name: str; fn: Callable; kind: str  # 'reference_free'|'reference_based'|'artifact'
    higher_is_better: bool = True; version: int = 1

REGISTRY: dict[str, MetricSpec] = {}
def metric(name, *, kind, higher_is_better=True, version=1): ...   # registers fn
def get_metric(name) -> MetricSpec: ...
```

First metrics (turn existing ad-hoc computations into named, versioned functions):
- `mean_prediction_confidence`, `frac_low_confidence` — currently inline in
  `cell_annotater_agent/tools_impl/harmony_transfer.py`.
- `n_shared_genes`, `n_cells`, `file_exists`, `csv_nonempty` — artifact/coverage checks.
- `ari`, `f1_macro` — annotation vs golden labels (`sklearn.metrics`).
- `abundance_jsd` — per-spot Jensen-Shannon between predicted and golden abundance matrices.

## C. Benchmark spec (markdown + frontmatter — reuse `parse_yaml_frontmatter`)

```markdown
---
name: visium_decon_lymphnode
status: enabled
tier: pipeline                 # 'tool' | 'pipeline'
task: spatial_deconvolution    # plan template / capability under test
prompt: |                      # required for tier=pipeline; omit for tier=tool
  Deconvolve the Visium slide at uploads/visium.h5ad using the reference at
  uploads/reference.h5ad. Use cell_type as the reference label column.
inputs:                        # dest-in-project : source-in-cache
  uploads/visium.h5ad:    library/benchmarks/lymphnode/visium.h5ad
  uploads/reference.h5ad: library/benchmarks/lymphnode/reference.h5ad
run_config:                    # tier=pipeline
  mode: autopilot
  model: default
  recursion_limit: 100
census_version: "2024-07-01"   # pin if the benchmark exercises the CELLxGENE fetch path
golden:
  abundances: library/benchmarks/lymphnode/expected/q05.csv
metrics:
  - { name: file_exists,   args: { path: q05_cell_abundance_w_sf.csv }, threshold: { eq: true } }
  - { name: abundance_jsd, threshold: { lte: 0.15 } }
---
## Notes
Human lymph node, ~30 cells/spot. Source: 10x public (see manifest.yaml).
```

For `tier: tool`, the spec instead names the tool + explicit args:

```yaml
tier: tool
tool: harmony_transfer_tool
args: { spatial_anndata_path: uploads/spatial.h5ad,
        reference_anndata_path: uploads/reference.h5ad,
        cell_type_column: cell_type }
golden: { labels: .../expected/labels.csv }
metrics:
  - { name: ari, threshold: { gte: 0.6 } }
```

## Runners

Both runners share `fixture.py` (materialize) and `score.py` (resolve + compare).

**`fixture.py`** — per benchmark: create an isolated temp project (`session.ensure_project_id()`
or a dedicated `bench_<name>` id under `PROJECTS_DIR`), copy each `inputs` source → dest inside it,
and set `session.project_id`, `session.mode = "autopilot"`, model selection (re-`_compile_graph`
if model pinned), fresh `thread_id`. Tear down the temp project after scoring.

**`tool_runner.py`** (deterministic, cheap, CI-able) — resolve the tool fn from the agent
registry, call it with `args` (paths relative to the staged project), then score outputs vs
`golden`. No LLM. Tests the *analysis*.

**`pipeline_runner.py`** (token-cost, nondeterministic, manual/nightly) — build the fixture
including `prompt`, call `session.agent.invoke({"messages": [HumanMessage(prompt)]}, config)`,
then score `active_project_outputs()` artifacts vs `golden`. Tests *agent routing + tool use*
(does the planner pick the right task, does the recruiter wire the right agent/skill).

**`scorecard.py`** — append one JSONL row per run: `{benchmark, tier, commit (git rev-parse HEAD,
passed in), timestamp (passed in), metrics: {name: {value, threshold, pass}}, overall_pass}`.
`diff` compares the latest two runs of a benchmark to surface regressions.

## Datasets — download script + manifest (data outside git)

- `knowledge/benchmarks/manifest.yaml`: per dataset, `{url, sha256}` for each file + `expected/`.
- `scripts/fetch_benchmarks.py`: idempotent — skip files already present with matching checksum;
  download into `workspace/library/benchmarks/<name>/` (gitignored). Fail loudly on checksum
  mismatch.
- Benchmarks assume the cache is populated; the runner errors with a "run fetch_benchmarks first"
  message if an input is missing.

## Reproducibility caveat (encode deliberately)

`query_cellxgene_census_live_tool` / `retrieve_cellxgene_single_cell_tool` hit the **live**
CELLxGENE Census (`census_version="latest"`) — non-hermetic, drifts over time. Any benchmark that
exercises the "no reference → fetch from CELLxGENE" path must either set `census_version` to a
dated snapshot in its spec, or pre-stage the reference in `inputs` and not trigger the fetch. The
spec's `census_version` field makes this an explicit choice.

## Phase 1 deliverables

1. `eval_registry/metrics/` core: `@metric`, `REGISTRY`, `get_metric`, `MetricSpec` + the first
   metrics above (with unit tests in `tests/` — pure functions, deterministic).
2. `benchmarks/` spec loader + `fixture.py` + `score.py` + `scorecard.py`.
3. **Both runners**: `tool_runner.py` and `pipeline_runner.py`.
4. One worked benchmark per tier:
   - `tier: tool` → `harmony_transfer_tool` annotation vs golden labels (`ari`).
   - `tier: pipeline` → `spatial_deconvolution` from a prompt vs golden abundances
     (`file_exists`, `abundance_jsd`).
5. `manifest.yaml` + `scripts/fetch_benchmarks.py` for those two datasets.
6. A thin CLI: `python -m eval_registry.benchmarks run [--tier tool|pipeline] [name...]`,
   `... list`, `... diff <name>`.

## Critical files to reuse (do not reinvent)

- `agents.agent_utils.parse_yaml_frontmatter` — spec parsing (same as plans/skills).
- `config.PROJECTS_DIR`, `active_project_outputs()`, `active_project_root()` — workspace paths.
- `server.session_manager.session` — `project_id`, `mode`, `agent`, `thread_id`,
  `ensure_project_id()`.
- `server.main._compile_graph` — rebuild the graph after pinning a model.
- Agent registry tool lists (e.g. `CellAnnotaterTools`, `SpotTools`) — resolve tool fns by name
  for `tier: tool`.

## Verification

- **Metrics**: `pytest tests/test_eval_metrics.py` — deterministic golden-vs-pred cases
  (known ARI, known JSD, file_exists true/false). Runs in default CI.
- **Tool benchmark**: `python -m eval_registry.benchmarks run --tier tool` with the cached
  dataset → expect `overall_pass: true`, scorecard row appended. Deterministic; CI-able once data
  is cached.
- **Pipeline benchmark**: `python -m eval_registry.benchmarks run --tier pipeline` (requires
  kernel gateway + LLM creds + Docker/local sandbox) → real graph runs, artifacts produced,
  scored. Manual/nightly, not default CI.
- **Regression flow**: run a tier-tool benchmark, change a tool/prompt, re-run,
  `... diff <name>` shows the metric delta.
```
