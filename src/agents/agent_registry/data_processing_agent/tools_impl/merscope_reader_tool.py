import anndata
import argparse
import numpy as np
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

    region = "region_0"
    slide_id = f"{dataset_dir.name}_{region}"

    data_dir = dataset_dir / "cell_by_gene.csv"
    obs_dir = dataset_dir / "cell_metadata.csv"

    if not data_dir.exists() or not obs_dir.exists():
        return f"Error: Did not find required files inside {dataset_dir}."

    data = pd.read_csv(data_dir, index_col=0, dtype={"cell": str})
    obs = pd.read_csv(obs_dir, index_col=0, dtype={"EntityID": str})

    obs.index = obs.index.astype(str) + f"_{slide_id}"
    data.index = data.index.astype(str) + f"_{slide_id}"
    obs = obs.loc[data.index]

    is_gene = ~data.columns.str.lower().str.contains("blank")

    adata = anndata.AnnData(data.loc[:, is_gene], dtype=np.uint16, obs=obs)

    adata.obsm["spatial"] = adata.obs[["center_x", "center_y"]].values
    adata.obs["region"] = pd.Series(region, index=adata.obs_names, dtype="category")
    adata.obs["slide_id"] = pd.Series(slide_id, index=adata.obs_names, dtype="category")

    adata.X = csr_matrix(adata.X)
    adata.write_h5ad(res_path)

    return f"Success: Created file at path {res_path}."


def main(args):
    path = Path(args.path).absolute() / "merscope"
    print(convert_to_h5ad(dataset_dir=path))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'merscope' directory)",
    )

    main(parser.parse_args())
