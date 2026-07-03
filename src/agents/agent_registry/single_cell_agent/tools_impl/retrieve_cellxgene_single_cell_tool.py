"""Download CELLxGENE Census source h5ad files into the active project."""

import cellxgene_census

from config import DATA_DIR, active_project_outputs


def retrieve_cellxgene_single_cell(dataset_id: str, filename: str):
    """Download a CELLxGENE dataset as an h5ad into the project's outputs/.

    Args:
        dataset_id: CELLxGENE Census dataset identifier.
        filename: Target filename. Lands at
            ``project/outputs/datasets/<filename>`` so the user
            can see the downloaded dataset in the Files panel and the
            agent can read it back from a stable relative path.

    Returns:
        Success or error message string. The returned path is relative
        to the workspace root.
    """
    outputs = active_project_outputs() / "datasets"
    outputs.mkdir(parents=True, exist_ok=True)
    filepath = outputs / filename
    if filepath.exists():
        relative = filepath.relative_to(DATA_DIR.resolve())
        return f"Error: file {relative.as_posix()} already exists"
    try:
        cellxgene_census.download_source_h5ad(
            dataset_id,
            str(filepath),
            census_version="latest",
            progress_bar=True,
        )
    except Exception as e:
        return f"Error: {e}"
    relative = filepath.relative_to(DATA_DIR.resolve())
    return f"Success: dataset with id {dataset_id} saved to {relative.as_posix()}"
