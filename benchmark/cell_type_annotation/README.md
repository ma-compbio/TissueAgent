# Cell annotation benchmarks

This package contains the annotation benchmark runners, preparation and evaluation
code, manifests, label mappings, and configuration previously under `demo/`.
See the [benchmark guide](../../docs/cell_annotation_agent_baselines.md) for setup
and complete commands, and [notebooks](../../notebooks/README.md) for interactive use.

- `data/`: local source data and prepared evaluation inputs.
- `outputs/`: benchmark runs and the committed compact baseline comparison.
- `manifests/`, `mappings/`, `configs/`: versioned benchmark definitions.

Run modules from the repository root with the source directory on the Python path:

```bash
PYTHONPATH=src python -m benchmark.cell_type_annotation.bcl --help
PYTHONPATH=src python -m benchmark.cell_type_annotation.run_agent_baseline_comparison --help
```

Large datasets and local run payloads remain ignored by Git. Frozen label mappings
and archived provenance retain their original recorded paths and checksums; active
manifests and runners use the current locations.

