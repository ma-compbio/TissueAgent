import anndata
import argparse
import pandas as pd

from pathlib import Path
from spatialdata_io.readers.xenium import _get_tables_and_circles
from typing import Union

from config import DATA_DIR


def convert_to_h5ad(dataset_dir: Union[Path, str]) -> str:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = DATA_DIR / dataset_dir
    res_path = dataset_dir / "adata.h5ad"

    if res_path.exists():
        return f"Error: File {res_path} already exists."

    adata: anndata.AnnData = _get_tables_and_circles(dataset_dir, False, {"region": "region_0"})
    adata.obs["cell_id"] = adata.obs["cell_id"].apply(
        lambda x: x if (isinstance(x, str) or isinstance(x, int)) else x.decode("utf-8")
    )

    slide_id = dataset_dir.name
    adata.obs.index = adata.obs["cell_id"].astype(str).values + f"_{slide_id}"

    adata.obs["slide_id"] = pd.Series(slide_id, index=adata.obs_names, dtype="category")

    adata.write_h5ad(res_path)

    return f"Success: Created file at path {res_path}."


def main(args):
    path = Path(args.path).absolute() / "xenium"
    print(convert_to_h5ad(dataset_dir=path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'xenium' directory)",
    )

    main(parser.parse_args())
