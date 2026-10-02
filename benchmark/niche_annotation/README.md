# Tissue-niche annotation benchmarks

This package contains the tissue-niche preparation, baseline runners, evaluation,
plotting code, manifests, and configuration previously under `demo/`.
See the [benchmark guide](../../docs/tissue_niche_agent_baselines.md) and
[interactive notebook](../../notebooks/tissue_niche_agent_baselines.ipynb).

- `data/raw/`: downloaded niche datasets.
- `data/agent_prepared/`: prepared inputs and private evaluation truth.
- `outputs/agent_comparisons/`: study outputs.
- `agent_manifests/`, `configs/`: versioned dataset and study definitions.

The heart manifest uses the shared input under
`benchmark/cell_type_annotation/data/inputs/developing_human_heart/`.
Large datasets and local run payloads remain ignored by Git.

Run modules from the repository root:

```bash
PYTHONPATH=src python -m benchmark.niche_annotation.spatialfusion_ovca --help
PYTHONPATH=src python -m benchmark.niche_annotation.run_agents --help
```
