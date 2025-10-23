import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import decoupler as dc
    import liana as li
    import matplotlib.pyplot as mpl
    import pandas as pd
    import scanpy as sc
    import squidpy as sq
    from pathlib import Path

    from liana.method import MistyData, genericMistyData, lrMistyData
    from liana.method.sp import RandomForestModel, LinearModel, RobustLinearModel

    dataset_path = Path("/Users/dustinm/Projects/research/ma-lab/SpatialAgent/test/datasets/lohoff_et_al_seqfish.h5ad")
    return dataset_path, sc


@app.cell
def _(dataset_path, sc):
    adata = sc.read_h5ad(dataset_path)
    adata.obs.head()
    return (adata,)


@app.cell
def _():
    # sc.pp.filter_cells(adata, min_genes=200)
    # sc.pp.filter_genes(adata, min_cells=3)
    return


@app.cell
def _(adata, sc):
    sc.pl.spatial(adata, color=["celltype_mapped_refined"], spot_size=0.08, palette="Set1")
    return


@app.cell
def _(adata, condition_key, groupby, sample_key, sc):
    sc.pl.umap(adata, color=[condition_key, sample_key, 'cell_type', groupby], frameon=False, ncols=2)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
