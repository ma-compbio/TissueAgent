"""Cell2location Visium spatial deconvolution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import scanpy as sc
from cell2location.models import Cell2location, RegressionModel
from config import DATA_DIR


@dataclass
class Cell2locationResultPaths:
    """Collection of key output artifacts produced by cell2location."""

    output_dir: Path
    reference_model_dir: Path
    spatial_model_dir: Path
    cell_abundance_q05: Optional[Path]
    cell_abundance_mean: Optional[Path]
    visium_h5ad: Path
    reference_h5ad: Path


def _resolve_path(path_like: str) -> Path:
    """Resolve a relative or absolute path against DATA_DIR."""
    path = Path(path_like)
    if not path.is_absolute():
        path = DATA_DIR / path
    return path


def _ensure_counts_layer(adata: sc.AnnData, layer_name: Optional[str]) -> Optional[str]:
    """Validate that layer_name exists in the AnnData, or pass through None."""
    if layer_name is None:
        return None
    if layer_name not in adata.layers:
        raise ValueError(f"Layer '{layer_name}' not found in AnnData object.")
    return layer_name


def _extract_cell_state_df(
    regression_model: RegressionModel,
    reference_adata: sc.AnnData,
    cell_type_column: str,
) -> pd.DataFrame:
    """Robustly recover the inferred reference cell state signatures."""
    # Try the public helper first (available in recent releases)
    if hasattr(regression_model, "export_cell_state_df"):
        try:
            cell_state_df = regression_model.export_cell_state_df()
        except TypeError:
            cell_state_df = regression_model.export_cell_state_df(reference_adata)
        if isinstance(cell_state_df, pd.DataFrame):
            return cell_state_df

    # Fallback: use posterior summaries stored on the AnnData object
    varm_keys = [
        "means_per_cluster_mu_fg",
        "means_per_cluster_mu_fg_var",
        "cell_type_means",
    ]
    for key in varm_keys:
        if key in reference_adata.varm:
            data = reference_adata.varm[key]
            if hasattr(data, "toarray"):
                data = data.toarray()
            mod_uns = (
                reference_adata.uns.get("mod", {}) if isinstance(reference_adata.uns, dict) else {}
            )
            factor_names = mod_uns.get("factor_names")
            if factor_names is None and cell_type_column in reference_adata.obs:
                labels = reference_adata.obs[cell_type_column]
                if hasattr(labels, "cat") and labels.cat is not None:
                    factor_names = list(labels.cat.categories.astype(str))
                else:
                    factor_names = list(pd.Index(labels.astype(str).unique()))
            if factor_names is None:
                factor_names = [f"factor_{i}" for i in range(data.shape[1])]
            cell_state_df = pd.DataFrame(
                data,
                index=reference_adata.var_names,
                columns=factor_names,
            )
            return cell_state_df

    raise RuntimeError(
        "Unable to extract cell state signatures from the regression model posterior."
    )


def _save_cell_abundance(
    adata_visium: sc.AnnData,
    output_dir: Path,
    basename: str,
    cell_state_df: pd.DataFrame,
) -> Optional[Path]:
    """Export a cell-abundance obsm matrix to CSV, returning the written path or None."""
    matrix = adata_visium.obsm.get(basename)
    if matrix is None:
        return None

    if isinstance(matrix, pd.DataFrame):
        abundance_df = matrix
    else:
        abundance_df = pd.DataFrame(
            matrix, index=adata_visium.obs_names, columns=cell_state_df.columns
        )

    path = output_dir / f"{basename}.csv"
    abundance_df.to_csv(path)
    return path


def run_cell2location_visium_deconvolution(
    visium_h5ad_path: str,
    reference_h5ad_path: str,
    output_subdir: str = "cell2location_results",
    cell_type_column: str = "cell_type",
    reference_batch_key: Optional[str] = None,
    reference_count_layer: Optional[str] = None,
    visium_batch_key: Optional[str] = None,
    visium_count_layer: Optional[str] = None,
    n_cells_per_location: float = 30.0,
    detection_alpha: float = 20.0,
    regression_max_epochs: int = 250,
    spatial_max_epochs: int = 3000,
    posterior_samples: int = 1000,
    posterior_batch_size: int = 2048,
    use_gpu: Optional[bool] = None,
) -> Dict[str, str]:
    """Run cell2location to deconvolve Visium spots into cell type abundances."""
    visium_path = _resolve_path(visium_h5ad_path)
    reference_path = _resolve_path(reference_h5ad_path)
    if not visium_path.exists():
        return {"status": "error", "message": f"Visium file not found: {visium_path}"}
    if not reference_path.exists():
        return {
            "status": "error",
            "message": f"Reference file not found: {reference_path}",
        }

    output_dir = _resolve_path(output_subdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        adata_ref = sc.read(reference_path)
        adata_vis = sc.read(visium_path)
    except Exception as exc:  # pragma: no cover - I/O errors bubble up
        return {
            "status": "error",
            "message": f"Failed to read input AnnData files: {exc}",
        }

    if cell_type_column not in adata_ref.obs:
        return {
            "status": "error",
            "message": f"Reference AnnData is missing the required '{cell_type_column}' column in .obs",
        }

    shared_genes = adata_ref.var_names.intersection(adata_vis.var_names)
    if len(shared_genes) < 50:
        return {
            "status": "error",
            "message": "Fewer than 50 shared genes between reference and Visium data after intersection.",
        }

    adata_ref = adata_ref[:, shared_genes].copy()
    adata_vis = adata_vis[:, shared_genes].copy()

    try:
        reference_layer = _ensure_counts_layer(adata_ref, reference_count_layer)
        visium_layer = _ensure_counts_layer(adata_vis, visium_count_layer)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    # Configure and train regression model on the reference scRNA-seq data
    setup_kwargs = {"labels_key": cell_type_column}
    if reference_layer is not None:
        setup_kwargs["layer"] = reference_layer
    if reference_batch_key is not None:
        setup_kwargs["batch_key"] = reference_batch_key

    RegressionModel.setup_anndata(adata_ref, **setup_kwargs)
    regression_model = RegressionModel(adata_ref)
    regression_model.train(max_epochs=regression_max_epochs, use_gpu=use_gpu)
    regression_model_dir = output_dir / "reference_regression_model"
    regression_model.save(regression_model_dir, overwrite=True)
    regression_model.export_posterior(
        adata_ref,
        sample_kwargs={
            "num_samples": posterior_samples,
            "batch_size": posterior_batch_size,
        },
    )
    cell_state_df = _extract_cell_state_df(regression_model, adata_ref, cell_type_column)

    # Configure and train the spatial deconvolution model
    setup_spatial_kwargs: Dict[str, object] = {}
    if visium_layer is not None:
        setup_spatial_kwargs["layer"] = visium_layer
    if visium_batch_key is not None:
        setup_spatial_kwargs["batch_key"] = visium_batch_key

    Cell2location.setup_anndata(adata_vis, **setup_spatial_kwargs)
    spatial_model = Cell2location(
        adata_vis,
        cell_state_df=cell_state_df,
        n_cells_per_location=n_cells_per_location,
        detection_alpha=detection_alpha,
    )
    spatial_model.train(max_epochs=spatial_max_epochs, use_gpu=use_gpu)
    spatial_model_dir = output_dir / "spatial_model"
    spatial_model.save(spatial_model_dir, overwrite=True)
    spatial_model.export_posterior(
        adata_vis,
        sample_kwargs={
            "num_samples": posterior_samples,
            "batch_size": posterior_batch_size,
        },
    )

    q05_path = _save_cell_abundance(adata_vis, output_dir, "q05_cell_abundance_w_sf", cell_state_df)
    mean_path = _save_cell_abundance(
        adata_vis, output_dir, "means_cell_abundance_w_sf", cell_state_df
    )

    visium_output = output_dir / "visium_with_cell2location.h5ad"
    reference_output = output_dir / "reference_with_posteriors.h5ad"
    adata_vis.write(visium_output, compression="gzip")
    adata_ref.write(reference_output, compression="gzip")

    result = Cell2locationResultPaths(
        output_dir=output_dir,
        reference_model_dir=regression_model_dir,
        spatial_model_dir=spatial_model_dir,
        cell_abundance_q05=q05_path,
        cell_abundance_mean=mean_path,
        visium_h5ad=visium_output,
        reference_h5ad=reference_output,
    )

    # Build structured response dictionary
    response: Dict[str, str] = {
        "status": "success",
        "output_dir": str(result.output_dir),
        "reference_model_dir": str(result.reference_model_dir),
        "spatial_model_dir": str(result.spatial_model_dir),
        "visium_h5ad": str(result.visium_h5ad),
        "reference_h5ad": str(result.reference_h5ad),
    }
    if result.cell_abundance_q05 is not None:
        response["cell_abundance_q05_csv"] = str(result.cell_abundance_q05)
    if result.cell_abundance_mean is not None:
        response["cell_abundance_mean_csv"] = str(result.cell_abundance_mean)

    return response
