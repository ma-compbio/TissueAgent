"""Download CELLxGENE Census source h5ad files to the local DATA_DIR."""

import cellxgene_census

from config import DATA_DIR


def retrieve_cellxgene_single_cell(dataset_id: str, filename: str):
    """Download a CELLxGENE dataset as an h5ad file into DATA_DIR.

    Args:
        dataset_id: CELLxGENE Census dataset identifier.
        filename: Target filename within DATA_DIR.

    Returns:
        Success or error message string.
    """
    filepath = DATA_DIR / filename
    if filepath.exists():
        return f"Error: filepath {filepath} already exists"
    try:
        cellxgene_census.download_source_h5ad(
            dataset_id,
            str(filepath),
            census_version="latest",
            progress_bar=True,
        )
    except Exception as e:
        return f"Error: {e}"
    return f"Success: dataset with id {dataset_id} saved to {filepath}"
