from __future__ import annotations

from typing import Dict
from pathlib import Path
import json
import time
import scanpy as sc
import pandas as pd
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
import mygene
import matplotlib.pyplot as plt
import anndata as ad
import matplotlib

from config import DATA_DIR, DATASET_DIR, UPLOADS_DIR


def _relative_to_data_dir(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(DATA_DIR.resolve()))
    except ValueError:
        return str(resolved)


def _resolve_path(path_like: str, *, must_exist: bool) -> Path:
    """
    Resolve a user-provided path into DATA_DIR while allowing references to common
    subdirectories created by the app (e.g. dataset/ or uploads/). Always enforces
    that the final target stays within DATA_DIR.
    """
    raw_path = Path(path_like).expanduser()
    data_root = DATA_DIR.resolve()

    candidate_roots = [
        None if raw_path.is_absolute() else DATA_DIR,
        None if raw_path.is_absolute() else DATASET_DIR,
        None if raw_path.is_absolute() else UPLOADS_DIR,
    ]

    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        for root in candidate_roots:
            if root is None:
                continue
            candidates.append(root / raw_path)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)
        try:
            resolved_candidate.relative_to(data_root)
        except ValueError:
            continue
        if must_exist and not resolved_candidate.exists():
            continue
        return resolved_candidate

    if must_exist:
        searched_locations = [str((root / raw_path).resolve()) for root in {DATA_DIR, DATASET_DIR, UPLOADS_DIR}]
        raise FileNotFoundError(
            f"Path '{path_like}' not found inside DATA_DIR '{DATA_DIR}'. "
            f"Searched: {', '.join(sorted(searched_locations))}"
        )

    target = (raw_path if raw_path.is_absolute() else DATA_DIR / raw_path).resolve()
    try:
        target.relative_to(data_root)
    except ValueError as exc:
        raise ValueError(
            f"Output path '{path_like}' must be inside DATA_DIR '{DATA_DIR}'."
        ) from exc
    return target


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

    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        reference_path = _resolve_path(reference_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        output_dir_path = _resolve_path(output_dir, must_exist=False)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Load datasets
    adata_spatial = sc.read(spatial_path)
    adata_ref = sc.read(reference_path)
    
    if cell_type_column not in adata_ref.obs:
        return {
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
            return {
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

        # Create standardized TSV outputs
        labels_tsv_path = output_dir_path / "labels.tsv"
        labels_tsv_path.parent.mkdir(parents=True, exist_ok=True)
        labels_df = results_df.rename(
            columns={"cell_id": "spot_id", "predicted_cell_type": "label"}
        )[["spot_id", "label"]]
        labels_df.to_csv(labels_tsv_path, sep="\t", index=False)

        tables_dir = DATA_DIR / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        confidence_tsv_path = tables_dir / "label_confidence.tsv"
        confidence_df = results_df.rename(
            columns={"cell_id": "spot_id", "prediction_confidence": "confidence"}
        )[["spot_id", "confidence"]]
        confidence_df.to_csv(confidence_tsv_path, sep="\t", index=False)

        # # # Add predictions to spatial AnnData and save
        adata_spatial.obs['harmony_predicted_cell_type'] = predictions
        adata_spatial.obs['harmony_prediction_confidence'] = prediction_confidence
        adata_spatial.obs['label'] = adata_spatial.obs['harmony_predicted_cell_type']
        
        spatial_output_path = output_dir_path / "spatial_with_harmony_labels.h5ad"
        adata_spatial.write(spatial_output_path, compression="gzip")

        annotated_output_path = output_dir_path / "annotated_object.h5ad"
        adata_spatial.write(annotated_output_path, compression="gzip")
        
        # Save reference with Harmony-corrected PCA
        reference_output_path = output_dir_path / "reference_with_harmony_pca.h5ad"
        adata_ref.obsm['X_pca_harmony'] = X_ref_pca
        adata_ref.write(reference_output_path, compression="gzip")

        # Generate spatial visualization
        figures_dir = DATA_DIR / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        figure_path = figures_dir / "spatial_labels.png"

        plot_labels = adata_spatial.obs['label'].astype(str)
        coords = adata_spatial.obsm.get("spatial")
        coords_array = None
        if coords is not None:
            coords_array = np.asarray(coords)

        fig = None
        if coords_array is not None and coords_array.shape[1] >= 2:
            fig, ax = plt.subplots(figsize=(6, 6))
            categories = plot_labels.astype("category").cat.categories.tolist()
            palette = plt.get_cmap("tab20")
            palette_colors = [
                palette(i / max(1, len(categories) - 1)) for i in range(len(categories))
            ]
            color_map = dict(zip(categories, palette_colors))

            max_points = 100000
            if adata_spatial.n_obs > max_points:
                sampled_indices = np.random.choice(
                    adata_spatial.n_obs, size=max_points, replace=False
                )
                sample_coords = coords_array[sampled_indices]
                sample_labels = plot_labels.iloc[sampled_indices]
            else:
                sample_coords = coords_array
                sample_labels = plot_labels

            for label in sample_labels.astype("category").cat.categories.tolist():
                mask = sample_labels == label
                if mask.sum() == 0:
                    continue
                ax.scatter(
                    sample_coords[mask, 0],
                    sample_coords[mask, 1],
                    s=5,
                    alpha=0.5,
                    label=label,
                    color=color_map.get(label, "#808080"),
                )
            ax.set_xlabel("spatial_x")
            ax.set_ylabel("spatial_y")
            ax.set_title("Spatial labels (sampled)")
            ax.legend(markerscale=3, bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="small")
        else:
            embedding_key = None
            for key in ("X_umap", "X_pca", "X_tsne"):
                if key in adata_spatial.obsm_keys():
                    embedding_key = key
                    break
            if embedding_key is not None:
                emb = adata_spatial.obsm[embedding_key]
                fig, ax = plt.subplots(figsize=(6, 6))
                categories = plot_labels.astype("category").cat.categories.tolist()
                palette = plt.get_cmap("tab20")
                palette_colors = [
                    palette(i / max(1, len(categories) - 1)) for i in range(len(categories))
                ]
                color_map = dict(zip(categories, palette_colors))
                for label in categories:
                    mask = plot_labels == label
                    if mask.sum() == 0:
                        continue
                    ax.scatter(
                        emb[mask, 0],
                        emb[mask, 1],
                        s=5,
                        alpha=0.5,
                        label=label,
                        color=color_map.get(label, "#808080"),
                    )
                ax.set_title(f"{embedding_key[2:].upper()} labels")
                ax.set_xlabel("component_1")
                ax.set_ylabel("component_2")
                ax.legend(markerscale=3, bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="small")
            else:
                fig, ax = plt.subplots(figsize=(6, 3))
                ax.text(
                    0.5,
                    0.5,
                    "No spatial/embedding coordinates available for plotting.",
                    ha="center",
                    va="center",
                )
                ax.axis("off")

        if fig is not None:
            fig.tight_layout()
            fig.savefig(figure_path, dpi=200, bbox_inches="tight")
            plt.close(fig)

        # Write run metadata
        logs_dir = DATA_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        meta_path = logs_dir / "run_meta.json"
        metadata = {
            "status": "success",
            "method": "Harmony integration + MLP classifier",
            "parameters": {
                "skip_preprocessing": skip_preprocessing,
                "min_genes": min_genes,
                "min_cells": min_cells,
                "target_sum": target_sum,
                "n_top_genes": n_top_genes,
                "n_pcs": n_pcs,
                "harmony_key": harmony_key,
                "mlp_hidden_layers": list(mlp_hidden_layers),
                "mlp_max_iter": mlp_max_iter,
                "mlp_random_state": mlp_random_state,
                "map_spatial_gene_names": map_spatial_gene_names,
            },
            "runtime": {
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "library_versions": {
                    "scanpy": sc.__version__,
                    "anndata": ad.__version__,
                    "pandas": pd.__version__,
                    "numpy": np.__version__,
                    "matplotlib": matplotlib.__version__,
                },
            },
            "inputs": {
                "spatial_anndata_path": _relative_to_data_dir(spatial_path),
                "reference_anndata_path": _relative_to_data_dir(reference_path),
            },
            "outputs": {
                "labels_csv": _relative_to_data_dir(csv_path),
                "labels_tsv": _relative_to_data_dir(labels_tsv_path),
                "label_confidence_tsv": _relative_to_data_dir(confidence_tsv_path),
                "spatial_annotated_h5ad": _relative_to_data_dir(spatial_output_path),
                "annotated_object_h5ad": _relative_to_data_dir(annotated_output_path),
                "reference_harmony_h5ad": _relative_to_data_dir(reference_output_path),
                "spatial_figure_png": _relative_to_data_dir(figure_path),
            },
            "summary": {
                "n_cells_transferred": int(len(predicted_labels)),
                "n_unique_cell_types": int(len(cell_type_counts)),
                "mean_prediction_confidence": float(np.mean(prediction_confidence)),
                "n_shared_genes": int(len(shared_genes)),
            },
        }
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)
        
        # Statistics
        cell_type_counts = pd.Series(predicted_labels).value_counts()
        
        return {
            "status": "success",
            "output_dir": _relative_to_data_dir(output_dir_path),
            "transferred_labels_csv": _relative_to_data_dir(csv_path),
            "spatial_annotated_h5ad": _relative_to_data_dir(spatial_output_path),
            "reference_harmony_h5ad": _relative_to_data_dir(reference_output_path),
            "labels_tsv": _relative_to_data_dir(labels_tsv_path),
            "annotated_object_h5ad": _relative_to_data_dir(annotated_output_path),
            "label_confidence_tsv": _relative_to_data_dir(confidence_tsv_path),
            "spatial_figure_png": _relative_to_data_dir(figure_path),
            "run_meta_json": _relative_to_data_dir(meta_path),
            "n_cells_transferred": len(predicted_labels),
            "n_unique_cell_types": len(cell_type_counts),
            "cell_type_counts": cell_type_counts.to_dict(),
            "mean_prediction_confidence": float(np.mean(prediction_confidence)),
            "n_shared_genes": len(shared_genes),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Harmony transfer failed: {str(e)}"
        }


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


def replace_var_names_with_mapping(adata: sc.AnnData, mapping_df: pd.DataFrame) -> sc.AnnData:
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
