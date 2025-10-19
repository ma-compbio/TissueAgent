import anndata
import argparse
import pandas as pd

from pathlib import Path
from scipy.sparse import csr_matrix
from typing import Union

from config import DATA_DIR

def convert_to_h5ad(dataset_dir: Union[Path, str]) -> str:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = DATA_DIR / dataset_dir
    res_path = dataset_dir / "adata.h5ad"

    if res_path.exists():
        return f"Error: File {res_path} already exists."

    slide_id = f"stereoseq_{dataset_dir.name}"

    h5ad_files = list(dataset_dir.glob("*.h5ad"))

    if len(h5ad_files) != 1:
        return f"Error: Found {len(h5ad_files)} h5ad file inside {dataset_dir}."

    adata = anndata.read_h5ad(h5ad_files[0])
    adata.X = adata.layers["raw_counts"]
    del adata.layers["raw_counts"]

    adata.obsm["spatial"] = adata.obsm["spatial"].astype(float).values
    adata.obs["slide_id"] = pd.Series(slide_id, index=adata.obs_names, dtype="category")

    adata.X = csr_matrix(adata.X)
    adata.write_h5ad(res_path)

    return f"Success: Created file at path {res_path}."


def main(args):
    path = Path(args.path).absolute() / "stereoseq"
    print(convert_to_h5ad(dataset_dir=path))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'stereoseq' directory)",
    )

    main(parser.parse_args())
