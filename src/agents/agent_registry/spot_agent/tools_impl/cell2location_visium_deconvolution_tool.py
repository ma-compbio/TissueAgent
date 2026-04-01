from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import numpy as np
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
    path = Path(path_like)
    if not path.is_absolute():
        path = DATA_DIR / path
    return path


def _ensure_counts_layer(adata: sc.AnnData, layer_name: Optional[str]) -> Optional[str]:
    if layer_name is None:
        return None
    if layer_name not in adata.layers:
        raise ValueError(f"Layer '{layer_name}' not found in AnnData object.")
    return layer_name


def _standardize_gene_ids(adata: sc.AnnData, prefer_ensembl: bool = True) -> sc.AnnData:
    """
    Standardize gene IDs to Ensembl format (ENSG...) if available.
    
    Checks common .var columns for Ensembl IDs and uses them as the index.
    Falls back to existing var_names if Ensembl IDs are not found.

    """
    # Common column names that might contain Ensembl IDs
    ensembl_columns = ['gene_ids', 'gene_id', 'ensembl_id', 'ensembl_gene_id', 
                       'ENSEMBL', 'feature_id', 'gene']
    
    # Check if var_names already look like Ensembl IDs
    if adata.var_names.str.match(r'^ENS[A-Z]*G\d{11}').sum() > adata.n_vars * 0.5:
        print(f"Gene IDs already appear to be Ensembl format (>50% match pattern)")
        return adata
    
    # Look for Ensembl IDs in .var columns
    ensembl_col = None
    for col in ensembl_columns:
        if col in adata.var.columns:
            # Check if this column contains Ensembl IDs
            if adata.var[col].astype(str).str.match(r'^ENS[A-Z]*G\d{11}').sum() > adata.n_vars * 0.5:
                ensembl_col = col
                print(f"Found Ensembl IDs in column: {col}")
                break
    
    if ensembl_col is not None and prefer_ensembl:
        # Store original gene names if not already stored
        if 'gene_symbol' not in adata.var.columns:
            adata.var['gene_symbol'] = adata.var_names
        
        # Set Ensembl IDs as index
        adata.var_names = adata.var[ensembl_col].astype(str)
        adata.var_names.name = 'gene_id'
        
        # Make unique if there are duplicates
        if not adata.var_names.is_unique:
            print(f"Warning: Found duplicate Ensembl IDs, making unique")
            adata.var_names_make_unique()
    else:
        print(f"No Ensembl IDs found in .var columns, using existing var_names")
        # If var_names are gene symbols, check if we have a column with Ensembl IDs to add
        if ensembl_col is not None:
            adata.var['ensembl_id'] = adata.var[ensembl_col]
    
    return adata


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

    print("Falling back to manual extraction of cell state signatures...")

    # Fallback: use posterior summaries stored on the AnnData object
    varm_keys = [
    "means_per_cluster_mu_fg",
    "means_per_cluster_mu_fg_var",   # keep for completeness, usually you want *mu_fg*
    "cell_type_means",
]
    for key in varm_keys:
        if key in reference_adata.varm:
            data = reference_adata.varm[key]
            print(f"  Trying to extract from varm key: '{key}'")
            print(f"  Data type: {type(data)}, shape: {data.shape}")

            # Get factor names
            mod_uns = reference_adata.uns.get("mod", {}) if isinstance(reference_adata.uns, dict) else {}
            factor_names = mod_uns.get("factor_names")
            if factor_names is None and cell_type_column in reference_adata.obs:
                labels = reference_adata.obs[cell_type_column]
                if hasattr(labels, "cat") and labels.cat is not None:
                    factor_names = list(labels.cat.categories.astype(str))
                else:
                    factor_names = list(pd.Index(labels.astype(str).unique()))
            if factor_names is None:
                # last resort
                factor_names = [f"factor_{i}" for i in range(data.shape[1])]
            
            print(f"  Factor names ({len(factor_names)}): {factor_names[:5]}..." if len(factor_names) > 5 else f"  Factor names: {factor_names}")

            # If data is a DataFrame (common), select the prefixed columns in the tutorial way
            if hasattr(data, "columns"):  # pandas DataFrame
                print(f"  Data is DataFrame with columns: {list(data.columns)[:5]}..." if len(data.columns) > 5 else f"  Data is DataFrame with columns: {list(data.columns)}")
                
                # Try different prefixing strategies
                prefixed = [f"{key}_{f}" for f in factor_names]
                missing = [c for c in prefixed if c not in data.columns]
                
                if missing:
                    print(f"  Warning: {len(missing)} prefixed columns not found in DataFrame")
                    # Try without the key prefix (sometimes data is already unprefixed)
                    if all(f in data.columns for f in factor_names):
                        print(f"  Found unprefixed factor names directly in columns")
                        df = data.loc[:, factor_names].copy()
                    elif key == "means_per_cluster_mu_fg":
                        # Sometimes factor_names are integers/strings; try strict str()
                        prefixed = [f"{key}_{str(f)}" for f in factor_names]
                        missing = [c for c in prefixed if c not in data.columns]
                        if not missing:
                            print(f"  Found columns with str() conversion")
                            df = data.loc[:, prefixed].copy()
                            df.columns = factor_names
                        else:
                            # Check if columns match the number of factors (might be in different order/format)
                            if data.shape[1] == len(factor_names):
                                print(f"  Column count matches factor count, using direct column order")
                                df = data.copy()
                                df.columns = factor_names
                            else:
                                print(f"  Column mismatch: {data.shape[1]} columns vs {len(factor_names)} factors")
                                print(f"  Falling back to numpy conversion")
                                arr = data.to_numpy()
                                df = pd.DataFrame(arr, index=reference_adata.var_names, columns=factor_names)
                    else:
                        # Last resort for DataFrame: convert to numpy
                        print(f"  Using numpy conversion as fallback")
                        arr = data.to_numpy()
                        df = pd.DataFrame(arr, index=reference_adata.var_names, columns=factor_names)
                else:
                    print(f"  Successfully matched all prefixed columns")
                    df = data.loc[:, prefixed].copy()
                    df.columns = factor_names
            else:
                # Not a DataFrame: coerce to numpy/sparse array and assign names
                print(f"  Data is not a DataFrame, converting to numpy")
                if hasattr(data, "to_numpy"):
                    arr = data.to_numpy()
                elif hasattr(data, "toarray"):
                    arr = data.toarray()
                else:
                    arr = data
                df = pd.DataFrame(arr, index=reference_adata.var_names, columns=factor_names)

            # Check if numeric before coercion
            print(f"  DataFrame shape: {df.shape}, dtypes: {df.dtypes.unique()}")
            
            # Only apply pd.to_numeric if data is not already numeric
            if not all(pd.api.types.is_numeric_dtype(df[col]) for col in df.columns):
                print(f"  Converting to numeric (some columns are non-numeric)")
                df = df.apply(pd.to_numeric, errors="coerce")
            
            # Check for NaN issues
            n_all_nan_cols = df.isna().all().sum()
            n_all_nan_rows = df.isna().all(axis=1).sum()
            print(f"  NaN check: {n_all_nan_cols} all-NaN columns, {n_all_nan_rows} all-NaN rows")
            
            if df.isna().all().all():
                print(f"  ERROR: {key} extracted but is all NaN after coercion")
                print(f"  Sample of original data:\n{data.iloc[:3, :3] if hasattr(data, 'iloc') else 'N/A'}")
                continue  # Try next key instead of raising error immediately
            
            print(f"  Successfully extracted cell state signatures from '{key}'")
            return df

    raise RuntimeError(
        "Unable to extract cell state signatures from the regression model posterior."
    )


def _save_cell_abundance(
    adata_visium: sc.AnnData,
    output_dir: Path,
    basename: str,
    cell_state_df: pd.DataFrame,
) -> Optional[Path]:
    matrix = adata_visium.obsm.get(basename)
    if matrix is None:
        return None

    if isinstance(matrix, pd.DataFrame):
        abundance_df = matrix
    else:
        abundance_df = pd.DataFrame(matrix, index=adata_visium.obs_names, columns=cell_state_df.columns)

    path = output_dir / f"{basename}.csv"
    abundance_df.to_csv(path)
    return path


def run_cell2location_visium_deconvolution(
    visium_h5ad_path: str,
    reference_h5ad_path: str,
    output_subdir: str = "cell2location_results",
    cell_type_column: str = "CellType",
    reference_batch_key: Optional[str] = None,
    reference_count_layer: Optional[str] = None,
    visium_batch_key: Optional[str] = None,
    visium_count_layer: Optional[str] = None,
    n_cells_per_location: float = 30.0,
    detection_alpha: float = 20.0,
    regression_max_epochs: int = 100,  # Reduced from 250 for faster training
    spatial_max_epochs: int = 1000,    # Reduced from 3000 for faster training
    learning_rate: float = 0.01,
    posterior_samples: int = 1000,
    posterior_batch_size: int = 2048,
    use_gpu: Optional[bool] = None,
    filter_genes: bool = True,
    min_cells_ref: int = 10,
    min_cells_vis: int = 10,
    min_counts: int = 10,
) -> Dict[str, str]:
    """Run cell2location to deconvolve Visium spots into cell type abundances."""

    if use_gpu is None:
        accelerator = "gpu" if sc.settings._default_backend == "pytorch-gpu" else "cpu"
    else:
        accelerator = "gpu" if use_gpu else "cpu"
    
    visium_path = _resolve_path(visium_h5ad_path)
    reference_path = _resolve_path(reference_h5ad_path)
    if not visium_path.exists():
        return {"status": "error", "message": f"Visium file not found: {visium_path}"}
    if not reference_path.exists():
        return {"status": "error", "message": f"Reference file not found: {reference_path}"}

    output_dir = _resolve_path(output_subdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        adata_ref = sc.read(reference_path)
        adata_vis = sc.read(visium_path)
    except Exception as exc:  # pragma: no cover - I/O errors bubble up
        return {"status": "error", "message": f"Failed to read input AnnData files: {exc}"}

    if cell_type_column not in adata_ref.obs:
        return {
            "status": "error",
            "message": f"Reference AnnData is missing the required '{cell_type_column}' column in .obs",
        }
    
    # Handle raw counts stored in .raw attribute for reference
    # If no count layer is specified and .raw exists, use it
    if reference_count_layer is None and hasattr(adata_ref, 'raw') and adata_ref.raw is not None:
        print("Found raw counts in adata_ref.raw, using for analysis...")
        # Convert .raw to the main matrix
        adata_ref = adata_ref.raw.to_adata()
        print(f"Using raw data: shape {adata_ref.shape}, dtype {adata_ref.X.dtype}")
    
    # Handle raw counts stored in .raw attribute for Visium
    # Cell2location requires raw integer counts, not normalized/log-transformed data
    if visium_count_layer is None and hasattr(adata_vis, 'raw') and adata_vis.raw is not None:
        print("Found raw counts in adata_vis.raw, using for analysis...")
        # Store the processed data for later visualization if needed
        adata_vis_processed = adata_vis.copy()
        # Convert .raw to the main matrix
        adata_vis = adata_vis.raw.to_adata()
        print(f"Using raw Visium data: shape {adata_vis.shape}, dtype {adata_vis.X.dtype}")
    
    # Check if data contains non-integer values (indicating normalization/log-transform)
    def check_raw_counts(adata, name="data"):
        """Check if data appears to be raw counts."""
        if hasattr(adata.X, 'data'):  # sparse matrix
            sample = adata.X.data[:1000]
        else:
            sample = adata.X.flat[:1000]
        
        # Check for non-integer values
        has_floats = not np.allclose(sample, np.round(sample))
        # Check for negative values
        has_negatives = np.any(sample < 0)
        # Check if values are in typical normalized range (0-10 for log-norm)
        max_val = np.max(sample)
        
        if has_floats or has_negatives or max_val < 20:
            print(f"  WARNING: {name} may not be raw counts:")
            print(f"    - Has non-integer values: {has_floats}")
            print(f"    - Has negative values: {has_negatives}")
            print(f"    - Max value in sample: {max_val:.2f}")
            return False
        return True
    
    print("\nChecking if data contains raw counts...")
    ref_is_raw = check_raw_counts(adata_ref, "Reference")
    vis_is_raw = check_raw_counts(adata_vis, "Visium")
    
    if not vis_is_raw:
        return {
            "status": "error",
            "message": "Visium data does not appear to contain raw integer counts. "
                      "Cell2location requires unnormalized count data. "
                      "Please ensure your Visium h5ad file contains raw counts in .X or specify a layer with raw counts using visium_count_layer parameter. "
                      "If raw counts are stored in .raw attribute, they will be used automatically."
        }
    
    if not ref_is_raw:
        return {
            "status": "error", 
            "message": "Reference data does not appear to contain raw integer counts. "
                      "Cell2location requires unnormalized count data. "
                      "Please ensure your reference h5ad file contains raw counts in .X or specify a layer with raw counts using reference_count_layer parameter. "
                      "If raw counts are stored in .raw attribute, they will be used automatically."
        }
    
    # Subset large reference datasets to a manageable size
    # If dataset has >100,000 cells, perform stratified sampling to maintain cell type distribution
    if adata_ref.n_obs > 100000:
        print(f"Reference dataset is large ({adata_ref.n_obs} cells). Performing stratified sampling...")
        
        # Target sample size
        target_size = 10000
        
        if cell_type_column not in adata_ref.obs.columns:
            print(f"Warning: cell_type_column '{cell_type_column}' not found. Performing random sampling.")
            # Random sampling without stratification
            sample_indices = np.random.choice(adata_ref.n_obs, size=min(target_size, adata_ref.n_obs), replace=False)
            adata_ref = adata_ref[sample_indices].copy()
        else:
            # Get original cell type distribution
            original_dist = adata_ref.obs[cell_type_column].value_counts()
            total_cells = adata_ref.n_obs
            
            print(f"Original cell type distribution ({total_cells} cells):")
            for ct, count in original_dist.head(10).items():
                print(f"  {ct}: {count} ({100*count/total_cells:.1f}%)")
            
            # Calculate proportional sample size for each cell type
            sampled_indices = []
            actual_samples = {}
            
            for cell_type in original_dist.index:
                # Calculate target number of cells for this type
                proportion = original_dist[cell_type] / total_cells
                n_samples = max(1, int(target_size * proportion))  # At least 1 cell per type
                
                # Get indices for this cell type
                ct_indices = np.where(adata_ref.obs[cell_type_column] == cell_type)[0]
                
                # Sample without replacement (or take all if fewer cells than target)
                n_to_sample = min(n_samples, len(ct_indices))
                sampled = np.random.choice(ct_indices, size=n_to_sample, replace=False)
                sampled_indices.extend(sampled)
                actual_samples[cell_type] = n_to_sample
            
            # Subset the data
            adata_ref = adata_ref[sampled_indices].copy()
            
            print(f"\nStratified sampling completed: {len(sampled_indices)} cells")
            print(f"New cell type distribution:")
            new_dist = adata_ref.obs[cell_type_column].value_counts()
            for ct, count in new_dist.head(10).items():
                orig_pct = 100 * original_dist[ct] / total_cells
                new_pct = 100 * count / len(sampled_indices)
                print(f"  {ct}: {count} ({new_pct:.1f}%, originally {orig_pct:.1f}%)")

    # Standardize gene IDs to Ensembl format in both datasets
    print("Standardizing gene IDs to Ensembl format...")
    adata_ref = _standardize_gene_ids(adata_ref, prefer_ensembl=True)
    adata_vis = _standardize_gene_ids(adata_vis, prefer_ensembl=True)
    
    # Ensure gene index is unique in both datasets
    if not adata_ref.var_names.is_unique:
        print("Making reference gene names unique...")
        adata_ref.var_names_make_unique()
    if not adata_vis.var_names.is_unique:
        print("Making Visium gene names unique...")
        adata_vis.var_names_make_unique()

    # Filter genes before intersection if requested
    if filter_genes:
        print("\nFiltering genes...")
        
        # Calculate QC metrics for reference
        n_genes_before_ref = adata_ref.n_vars
        sc.pp.calculate_qc_metrics(adata_ref, inplace=True)
        
        # Filter reference: genes expressed in at least min_cells_ref cells with min_counts total counts
        gene_filter_ref = (adata_ref.var['n_cells_by_counts'] >= min_cells_ref) & \
                         (adata_ref.var['total_counts'] >= min_counts)
        adata_ref = adata_ref[:, gene_filter_ref].copy()
        print(f"  Reference: {n_genes_before_ref} → {adata_ref.n_vars} genes "
              f"(removed {n_genes_before_ref - adata_ref.n_vars} low-quality genes)")
        
        # Calculate QC metrics for Visium
        n_genes_before_vis = adata_vis.n_vars
        sc.pp.calculate_qc_metrics(adata_vis, inplace=True)
        
        # Filter Visium: genes expressed in at least min_cells_vis spots with min_counts total counts
        gene_filter_vis = (adata_vis.var['n_cells_by_counts'] >= min_cells_vis) & \
                         (adata_vis.var['total_counts'] >= min_counts)
        adata_vis = adata_vis[:, gene_filter_vis].copy()
        print(f"  Visium: {n_genes_before_vis} → {adata_vis.n_vars} genes "
              f"(removed {n_genes_before_vis - adata_vis.n_vars} low-quality genes)")

    # Remove mitochondrial genes from Visium data before aligning
    print("\nRemoving mitochondrial genes from Visium data...")
    
    # Check if 'SYMBOL' column exists, otherwise use var_names
    if 'SYMBOL' in adata_vis.var.columns:
        gene_names = adata_vis.var['SYMBOL']
    elif 'gene_symbol' in adata_vis.var.columns:
        gene_names = adata_vis.var['gene_symbol']
    else:
        gene_names = adata_vis.var_names
    
    # Find mitochondria-encoded (MT) genes
    adata_vis.var['MT_gene'] = [str(gene).startswith('MT-') for gene in gene_names]
    n_mt_genes = sum(adata_vis.var['MT_gene'])
    print(f"  Found {n_mt_genes} mitochondrial genes")
    
    if n_mt_genes > 0:
        # Store MT gene counts in obsm for reference (keeping their counts in the object)
        adata_vis.obsm['MT'] = adata_vis[:, adata_vis.var['MT_gene'].values].X.toarray()
        
        # Remove MT genes for spatial mapping
        adata_vis = adata_vis[:, ~adata_vis.var['MT_gene'].values].copy()
        print(f"  Removed {n_mt_genes} MT genes, {adata_vis.n_vars} genes remaining")
        print(f"  Verification: {sum(adata_vis.var['MT_gene'])} MT genes in filtered data (should be 0)")

    shared_genes = adata_ref.var_names.intersection(adata_vis.var_names)
    print(f"Found {len(shared_genes)} shared genes between reference and Visium data")
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
    regression_model.train(max_epochs=regression_max_epochs, accelerator=accelerator, lr=learning_rate)
    regression_model_dir = output_dir / "reference_regression_model"
    regression_model.save(regression_model_dir, overwrite=True)
    regression_model.export_posterior(
        adata_ref,
        sample_kwargs={"num_samples": posterior_samples, "batch_size": posterior_batch_size},
    )


    cell_state_df = _extract_cell_state_df(regression_model, adata_ref, cell_type_column)
    cell_state_df = cell_state_df.loc[(cell_state_df.sum(axis=1) > 0), :]  # drop all-zero rows
    
    common = adata_vis.var_names.intersection(cell_state_df.index)
    if len(common) < 50:
        return {"status": "error",
            "message": f"Too few shared genes after cleaning: {len(common)}."}
    
    # Subset BOTH to the same gene set and ORDER
    adata_vis = adata_vis[:, common].copy()
    cell_state_df = cell_state_df.loc[common, :]
    cell_state_df = cell_state_df.loc[adata_vis.var_names, :]  # enforce identical order

    # (Optional) sanity checks
    assert (cell_state_df.index == adata_vis.var_names).all()
    assert cell_state_df.shape[0] == adata_vis.n_vars

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
        N_cells_per_location=n_cells_per_location,
        detection_alpha=detection_alpha,
    )
    spatial_model.train(max_epochs=spatial_max_epochs, accelerator=accelerator, lr=learning_rate)
    spatial_model_dir = output_dir / "spatial_model"
    spatial_model.save(spatial_model_dir, overwrite=True)
    spatial_model.export_posterior(
        adata_vis,
        sample_kwargs={"num_samples": posterior_samples, "batch_size": posterior_batch_size},
    )

    q05_path = _save_cell_abundance(adata_vis, output_dir, "q05_cell_abundance_w_sf", cell_state_df)
    mean_path = _save_cell_abundance(adata_vis, output_dir, "means_cell_abundance_w_sf", cell_state_df)

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