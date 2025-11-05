from __future__ import annotations

from typing import Dict, Optional, List
from pathlib import Path
import scanpy as sc
import pandas as pd
import numpy as np
from scipy import sparse
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
import pandas as pd
import mygene

from config import DATA_DIR


def _resolve_path(path_like: str) -> Path:
    path = Path(path_like)
    if not path.is_absolute():
        path = DATA_DIR / path
    return path


def harmony_transfer_tool(
    spatial_anndata_path: str,
    reference_anndata_path: str,
    output_dir: str = "harmony_transfer_results",
    cell_type_column: str = "cell_type",
    skip_preprocessing: bool = False,
    min_genes: int = 50,
    min_cells: int = 10,
    target_sum: float = 1e4,
    n_top_genes: int = 2000,
    n_pcs: int = 30,
    harmony_key: str = "batch",
    mlp_hidden_layers: tuple = (100, 50),
    mlp_max_iter: int = 500,
    mlp_random_state: int = 42,
    map_spatial_gene_names: bool = True,
) -> Dict[str, str]:
    
    spatial_path = _resolve_path(spatial_anndata_path)
    reference_path = _resolve_path(reference_anndata_path)
    output_dir_path = _resolve_path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    if not spatial_path.exists():
        m =  {"status": "error", "message": f"Spatial file not found: {spatial_path}"}
    if not reference_path.exists():
        m =  {"status": "error", "message": f"Reference file not found: {reference_path}"}
    
    # Load datasets
    adata_spatial = sc.read(spatial_path)
    adata_ref = sc.read(reference_path)
    
    if cell_type_column not in adata_ref.obs:
        m =  {
            "status": "error",
            "message": f"Reference missing '{cell_type_column}' column in .obs"
        }

    try:
        # Standardize gene names if requested
        if map_spatial_gene_names:
            adata_spatial_gene_names_mapping = map_genes(adata_spatial.var_names.to_list())
            adata_spatial = replace_var_names_with_mapping(adata_spatial,adata_spatial_gene_names_mapping)
            
        # Optionally preprocess datasets (recommended if inputs are raw)
        if not skip_preprocessing:
            adata_ref = _preprocess_dataset(
                adata_ref, min_genes, min_cells, target_sum, n_top_genes, "reference"
            )
            adata_spatial = _preprocess_dataset(
                adata_spatial, min_genes, min_cells, target_sum, n_top_genes, "spatial"
            )        
           # Find shared genes
        shared_genes = adata_ref.var_names.intersection(adata_spatial.var_names)
        if len(shared_genes) < 50:
            m =  {
                "status": "error",
                "message": f"Too few shared genes: {len(shared_genes)}. Need at least 50."
            }
        
        # Subset to shared genes
        adata_ref = adata_ref[:, shared_genes].copy()
        adata_spatial = adata_spatial[:, shared_genes].copy()
        
        # Combine datasets for Harmony integration
        adata_ref.obs[harmony_key] = "reference"
        adata_spatial.obs[harmony_key] = "spatial"
        adata_ref.obs["dataset"] = "reference"
        adata_spatial.obs["dataset"] = "spatial"
        
        
        # Combine into single AnnData
        adata_combined = adata_ref.concatenate(
            adata_spatial,
            batch_key=harmony_key,
            index_unique=None
        )
    
        # # Perform PCA on combined data
        sc.pp.pca(adata_combined, n_comps=n_pcs)
        
        # # Perform Harmony integration for batch correction
        sc.external.pp.harmony_integrate(adata_combined, key=harmony_key)
        
        # # # Extract Harmony-corrected PCA (use X_pca_harmony if available, else X_pca)
        harmony_pca_key = 'X_pca_harmony' if 'X_pca_harmony' in adata_combined.obsm else 'X_pca'
        
        # # Split back into reference and spatial
        reference_mask = adata_combined.obs['dataset'] == "reference"
        spatial_mask = adata_combined.obs['dataset'] == "spatial"
        
        X_ref_pca = adata_combined.obsm[harmony_pca_key][reference_mask]
        X_spatial_pca = adata_combined.obsm[harmony_pca_key][spatial_mask]
        
        # Get reference labels
        y_ref = adata_combined.obs.loc[reference_mask, cell_type_column].values
        
        # Train MLP classifier on reference PCA
        scaler = StandardScaler()
        X_ref_scaled = scaler.fit_transform(X_ref_pca)
        X_spatial_scaled = scaler.transform(X_spatial_pca)
        
        mlp = MLPClassifier(
            hidden_layer_sizes=mlp_hidden_layers,
            max_iter=mlp_max_iter,
            random_state=mlp_random_state,
            verbose=False
        )
        
        mlp.fit(X_ref_scaled, y_ref)
        
        # Predict cell types for spatial data
        predictions = mlp.predict(X_spatial_scaled)
        prediction_probs = mlp.predict_proba(X_spatial_scaled)
        
        # Get prediction confidence (max probability)
        prediction_confidence = np.max(prediction_probs, axis=1)
        
        # # # Get predicted class names
        predicted_labels = predictions
        
        # Save results to CSV
        results_df = pd.DataFrame({
            'cell_id': adata_spatial.obs_names,
            'predicted_cell_type': predictions,
            'prediction_confidence': prediction_confidence,
        })
        
        
        # # Save CSV
        csv_path = output_dir_path / "harmony_transferred_labels.csv"
        results_df.to_csv(csv_path, index=False)
        
        # # # Add predictions to spatial AnnData and save
        adata_spatial.obs['harmony_predicted_cell_type'] = predictions
        adata_spatial.obs['harmony_prediction_confidence'] = prediction_confidence
        
        spatial_output_path = output_dir_path / "spatial_with_harmony_labels.h5ad"
        adata_spatial.write(spatial_output_path, compression="gzip")
        
        # Save reference with Harmony-corrected PCA
        reference_output_path = output_dir_path / "reference_with_harmony_pca.h5ad"
        adata_ref.obsm['X_pca_harmony'] = X_ref_pca
        adata_ref.write(reference_output_path, compression="gzip")
        
        #  Statistics
        cell_type_counts = pd.Series(predicted_labels).value_counts()
        
        m= {
            "status": "success",
            "output_dir": str(output_dir_path),
            "transferred_labels_csv": str(csv_path),
            "spatial_annotated_h5ad": str(spatial_output_path),
            "reference_harmony_h5ad": str(reference_output_path),
            "n_cells_transferred": len(predicted_labels),
            "n_unique_cell_types": len(cell_type_counts),
            "cell_type_counts": cell_type_counts.to_dict(),
            "mean_prediction_confidence": float(np.mean(prediction_confidence)),
            "n_shared_genes": len(shared_genes),
        }
        return m
    except Exception as e:
        return {
            "status": "error",
            "message": f"Harmony transfer failed: {str(e)}"
        }


def _resolve_path(path_like: str) -> Path:
    path = Path(path_like)
    if not path.is_absolute():
        path = DATA_DIR / path
    return path


def _preprocess_dataset(
    adata: sc.AnnData,
    min_genes: int,
    min_cells: int,
    target_sum: float,
    n_top_genes: int,
    dataset_name: str,
    percent_top = (50,100,200)
) -> sc.AnnData:
    """Preprocess a single dataset: filter, normalize, log transform, select HVGs."""
    # Calculate QC metrics
    sc.pp.calculate_qc_metrics(adata,percent_top=percent_top, inplace=True)
    
    # Filter cells
    sc.pp.filter_cells(adata, min_genes=min_genes)
    
    # Filter genes
    sc.pp.filter_genes(adata, min_cells=min_cells)
    
    # Normalize
    sc.pp.normalize_total(adata, target_sum=target_sum)
    
    # Log transform
    sc.pp.log1p(adata)
    
    # Select highly variable genes
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, flavor='seurat')
    
    return adata




def map_genes(
    genes,
    species: str = "human",
    from_field: str = "symbol",
    to_field: str = "ensembl",
) -> pd.DataFrame:
    """
    Map gene identifiers using the MyGene.info API.

    Parameters
    ----------
    genes : list[str]
        List of gene identifiers to map.
    species : str, default="human"
        Species name or alias recognized by MyGene (e.g., "human", "mouse").
    from_field : str, default="symbol"
        The type of identifier being provided (e.g., "symbol", "ensembl.gene").
    to_field : str, default="ensembl.gene"
        The target identifier field to map to (e.g., "symbol", "entrezgene").

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: ["query", "mapped_id"] and potentially "notfound".
    """
    mg = mygene.MyGeneInfo()

    if 'ensembl' in to_field:
        to_field_query = to_field + '.gene'
    else:
        to_field_query = to_field
    # Query MyGene.info API
    results = mg.querymany(
        genes,
        scopes=from_field,
        fields=to_field_query,
        species=species,
        as_dataframe=False,
        returnall=False,
    )

    df = pd.DataFrame(results)

    # Extract the mapped ID (handling lists or dicts)
    def extract_mapped(x):
        if isinstance(x, list):
            # Take the first match if multiple
            x = x[0]
        if isinstance(x, dict):
            return x.get("gene") or x.get("primary") or next(iter(x.values()), None)
        return x

    if to_field in df.columns:
        df["mapped_id"] = df[to_field].apply(extract_mapped)
    else:
        df["mapped_id"] = None

    # Drop rows without a mapping
    df = df[["query", "mapped_id"]]
    df = df.drop_duplicates(subset=["query"])

    return df


def replace_var_names_with_mapping(adata: ad.AnnData, mapping_df: pd.DataFrame) -> ad.AnnData:
    """
    Replace adata.var_names (gene names) using a mapping DataFrame from map_genes().

    Parameters
    ----------
    adata : anndata.AnnData
        Input AnnData object whose var_names will be replaced.
    mapping_df : pd.DataFrame
        Must contain columns ["query", "mapped_id"] as returned by map_genes().

    Returns
    -------
    adata : anndata.AnnData
        A new AnnData object with updated var_names (mapped IDs).
    """

    # Ensure mapping_df has the expected columns
    if not {"query", "mapped_id"}.issubset(mapping_df.columns):
        raise ValueError("mapping_df must contain columns: ['query', 'mapped_id'].")

    # Create a mapping dict: {old_name -> new_name}
    mapping_dict = dict(zip(mapping_df["query"], mapping_df["mapped_id"]))

    # Ensure var_names is string type
    adata.var_names = adata.var_names.astype(str)

    # Map old → new names
    new_var_names = adata.var_names.map(mapping_dict)

    # Use Series.where to keep original names where mapping failed
    new_var_names = pd.Series(new_var_names, index=adata.var_names).where(
        pd.notnull(new_var_names), adata.var_names
    )

    # Ensure uniqueness (Scanpy requires unique var_names)
    adata.var_names = pd.Index(new_var_names)

    # Optional: store the original names
    adata.var["original_gene_symbol"] = adata.var_names.map(
        {v: k for k, v in mapping_dict.items()}
    )

    return adata