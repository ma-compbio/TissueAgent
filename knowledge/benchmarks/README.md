# Benchmarks

Markdown-specced benchmarks for the **eval registry**. Each `*.md` (except this README and the
`_example_*` placeholders) is one benchmark, parsed with the same YAML-frontmatter loader as
`plans/` and `skills/`. See [`../docs/eval_registry.md`](../docs/eval_registry.md) for the full
design and [`../../src/eval_registry/`](../../src/eval_registry/) for the metrics + runner.

## Two tiers

| | `tier: tool` | `tier: pipeline` |
|---|---|---|
| **Drives** | a tool function directly (`tool` + `args`) | the real graph from a `prompt` |
| **Tests** | the analysis in isolation | planner/recruiter routing + tool use |
| **LLM?** | No — deterministic | Yes — nondeterministic, costs tokens |
| **CI?** | Yes (once data is cached) | Manual / nightly |

Copy `_example_tool.md` or `_example_pipeline.md`, rename, and set `status: enabled`.

## Frontmatter fields

- **`name`** *(required)* — unique slug.
- **`status`** — `enabled` or `disabled` (default `enabled`; the `_example_*` files are disabled).
- **`tier`** *(required)* — `tool` or `pipeline`.
- **`task`** — the plan template / capability under test (for grouping/reporting).
- **`inputs`** — `dest-in-project: source-in-cache`; sources are populated by
  `scripts/fetch_benchmarks.py` from `manifest.yaml`.
- **`golden`** — ground-truth files for reference-based metrics.
- **`metrics`** — list of `{name, args?, threshold}`. `name` must exist in the metric registry
  (`eval_registry.metrics.REGISTRY`); `threshold` is one of `gte`/`lte`/`gt`/`lt`/`eq`.
- `tier: tool` adds **`tool`** + **`args`**.
- `tier: pipeline` adds **`prompt`** *(required)*, **`run_config`** (`mode`/`model`/`recursion_limit`),
  and optional **`census_version`** (pin when the live CELLxGENE fetch path is exercised).

## Datasets

Benchmark data lives **outside git**. `manifest.yaml` holds per-file `{url, sha256}`;
`scripts/fetch_benchmarks.py` downloads + checksums into `workspace/library/benchmarks/<name>/`
(gitignored). Run it before executing benchmarks that need cached inputs.
