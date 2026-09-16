# mLLMCelltype Agent

Adapter wrapping [mLLMCelltype](https://github.com/cafferychen777/mLLMCelltype)
(multi-LLM consensus cell-type annotation for scRNA-seq).

## What it does

Takes per-cluster marker-gene lists + a species and returns a cell-type label
per cluster. In `consensus` mode it queries several LLMs and also returns
per-cluster confidence (consensus proportion, Shannon entropy) and per-model
votes.

## Credentials

At least one of:

- `OPENAI_API_KEY` (preferred), or
- `ANTHROPIC_API_KEY`

resolved through TissueAgent's key registry (UI-pasted value or env var).

## Isolated environment (supported path)

mLLMCelltype needs `openai>=1.0`, which conflicts with TissueAgent's pinned
`openai<2.0`. Run it in its own conda env; the runner calls it there:

```bash
conda create -n mllmcelltype -y python=3.11
conda run -n mllmcelltype pip install "mllmcelltype[openai,anthropic]"
```

If that env is absent, the runner falls back to importing the pinned submodule
in-process (convenient for smoke tests; may hit the `openai` pin).

## Entry point

`runner.run_mllmcelltype_annotation(marker_genes, species, tissue=None,
mode="single", provider="openai", model=None, models=None,
additional_context=None)` → structured dict (see `tool.py`).

Upstream pinned commit: see `manifest.yaml` (`upstream.commit`).
