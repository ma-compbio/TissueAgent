import argparse
import stlearn as st

from pathlib import Path
from typing import Union

from config import DATA_DIR


def convert_to_h5ad(dataset_dir: Union[Path, str], puck_id: Optional[str] = None) -> str:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = DATA_DIR / dataset_dir
    res_path = dataset_dir / "adata.h5ad"

    if res_path.exists():
        return f"Error: File {res_path} already exists."

    count_file, spatial_file = "", ""
    if puck_id is None:
        count_files = {f.stem for f in dataset_dir.iterdir() if f.suffix == ".count"}
        spatial_files = {f.stem for f in dataset_dir.iterdir() if f.suffix == ".idx"}
        common_basenames = count_files & spatial_files

        if len(common_basenames) == 0:
            return "Error: Did not find a valid .count or .idx file."
        elif len(common_basenames) >= 2:
            return (
                "Error: Ambiguity in .count / .idx files to use. Please specify"
                "using the `puck_id` argument."
            )

        count_file = dataset_dir / count_files[0]
        spatial_file = dataset_dir / spatial_files[0]
    else:
        count_file = dataset_dir / f"{puck_id}.count"
        spatial_file = datset_dir / f"{puck_id}.idx"

    if not count_file.exists():
        return f"Error: Count matrix file {count_file} does not exist."
    if not spatial_file.exists():
        return f"Error: Spatial file {count_file} does not exist."

    adata = st.ReadSlideSeq(count_file, spatial_file)
    adata.write_h5ad(res_path)

    return f"Success: Created file at path {res_path}."


def main(args):
    path = Path(args.path).absolute() / "slideseq"
    print(convert_to_h5ad(dataset_dir=path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=".",
        help="Path to spatial directory (containing the 'slideseq' directory)",
    )

    main(parser.parse_args())
