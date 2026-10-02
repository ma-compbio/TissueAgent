# Annotation notebooks

Launch Jupyter from the repository root or this directory after setting up the
environment described in the [repository README](../README.md).

- [Cell annotation benchmark](cell_annotation_benchmark.ipynb): prepare and evaluate
  developing heart, BCL, and Han mouse brain datasets with TissueAgent and baselines.
- [Cell annotation with baselines](cell_annotation_w_baselines.ipynb): the original
  exploratory workflow; requires its mouse CNS and MERFISH inputs under
  `benchmark/cell_type_annotation/data/`.
- [Tissue-niche agent baselines](tissue_niche_agent_baselines.ipynb): compare
  TissueAgent, Biomni, and SpatialAgent on heart and ovarian tissue niches.

Cell annotation code, manifests, data, and outputs live in
[`benchmark/cell_type_annotation/`](../benchmark/cell_type_annotation/README.md).
Niche annotation code and its data/output defaults live in
[`benchmark/niche_annotation/`](../benchmark/niche_annotation/README.md).

