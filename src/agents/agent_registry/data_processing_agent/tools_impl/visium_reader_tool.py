import argparse
import squidpy as sq

from pathlib import Path
from typing import Union

from config import DATA_DIR

def convert_to_h5ad(dataset_dir: Union[Path, str]) -> str:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = DATA_DIR / dataset_dir
    res_path = dataset_dir / "adata.h5ad"

    if res_path.exists():
        return f"Error: File {res_path} already exists."

    counts_files = list(dataset_dir.glob("*filtered_feature_bc_matrix.h5"))

    if len(counts_files) == 0:
        return f"Error: Did not find count matrix file in {dataset_dir}."
    elif len(counts_files) > 1:
        return f"Error: Ambiguity in count file to be used."
    
    adata = sq.read.visium(str(dataset_dir),
                           counts_file=str(counts_files[0]))
    adata.write_h5ad(res_path)
  
    return f"Success: Created file at path {res_path}."

def main(args):
    path = Path(args.path).absolute() / "visium"
    print(convert_to_h5ad(dataset_dir=path))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'visium' directory)",
    )

    main(parser.parse_args())
