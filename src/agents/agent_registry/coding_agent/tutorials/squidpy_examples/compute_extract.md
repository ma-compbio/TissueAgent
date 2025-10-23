# Plot features in adata.obsm

This example shows how to use `squidpy.pl.extract` to plot features in
`anndata.AnnData.obsm`.

:::{seealso}

    See {doc}`examples/image/compute_summary_features` for
    computing an example of such features.
:::



```python
import squidpy as sq

adata = sq.datasets.slideseqv2()
adata
```

In this dataset, we have saved deconvolution results in
`anndata.AnnData.obsm` and we would like to plot them with
`squidpy.pl.spatial_scatter`.



```python
adata.obsm["deconvolution_results"].head(10)
```

Squidpy provides an easy wrapper that creates a temporary copy of the
feature matrix and pass it to `anndata.AnnData.obs`.



```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "deconvolution_results"),
    shape=None,
    color=["Astrocytes", "Mural", "CA1_CA2_CA3_Subiculum"],
    size=4,
)
```
