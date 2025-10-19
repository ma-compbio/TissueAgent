import argparse
import spatialdata_io as sd

from pathlib import Path
from typing import Union
from spatialdata_io.experimental import to_legacy_anndata

from config import DATA_DIR

def convert_to_h5ad(dataset_dir: Union[Path, str], filtered: bool=True) -> str:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = DATA_DIR / dataset_dir
    res_path = dataset_dir / "adata.h5ad"

    if res_path.exists():
        return f"Error: File {res_path} already exists."

    try:
        sdata = sd.visium_hd(dataset_dir)
    except Exception as e:
        return f"Error: Visium HD read failed with error {e}."

    for table in sdata.tables.values():
        table.var_names_make_unique()
    
    # by default, use smallest resolution possible
    table_name = min(map(str, sdata.tables))

    coordinate_system = "downscaled_hires"
    if coordinate_system not in sdata.coordinate_systems:
        return f"Error: High resolution coordinate system not found."

    try:
        adata = to_legacy_anndata(sdata,
                                  coordinate_system=coordinate_system,
                                  table_name=table_name)
    except Exception as e:
        return f"Error: AnnData conversion failed with error {e}."
    adata.write_h5ad(res_path)
  
    return f"Success: Created file at path {res_path}."

def main(args):
    path = Path(args.path).absolute() / "visiumhd"
    print(convert_to_h5ad(dataset_dir=path))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'visiumhd' directory)",
    )

    main(parser.parse_args())
