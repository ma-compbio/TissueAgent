---
title: "Plot features in adata.obsm"
keywords:
  - "squidpy"
  - "extract"
  - "obsm"
  - "spatial_scatter"
  - "plotting"
  - "deconvolution"
  - "visualization"
---

# Plot features in adata.obsm

This example shows how to use `squidpy.pl.extract` to plot features stored in `adata.obsm`.

```python
import squidpy as sq

adata = sq.datasets.slideseqv2()
adata
```

Inspect deconvolution results stored in `adata.obsm`.

```python
adata.obsm["deconvolution_results"].head(10)
```

Use `squidpy.pl.extract` to create a temporary copy of the feature matrix in `adata.obs` for plotting with `spatial_scatter`.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "deconvolution_results"),
    shape=None,
    color=["Astrocytes", "Mural", "CA1_CA2_CA3_Subiculum"],
    size=4,
)
```
