"""Package the cell comparison's input data for extraction at the repository root."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from .run_agent_baseline_comparison import ROOT, load_config


INPUT_ROOT = ROOT / "demo/data/cell_annotation/inputs"
DEFAULT_OUTPUT = INPUT_ROOT.parent / "cell_annotation_eval_inputs.zip"


def input_files() -> list[tuple[Path, str]]:
    """List only the query and external truth files declared by the comparison."""
    files = []
    for spec in load_config()["datasets"]:
        manifest_path = Path(__file__).with_name("manifests") / f"{spec['dataset_id']}.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        files.append((ROOT / manifest["query"]["path"], manifest["query"]["sha256"]))
        if "path" in manifest["ground_truth"]:
            files.append(
                (ROOT / manifest["ground_truth"]["path"], spec["expected_ground_truth_sha256"])
            )
    for path, _ in files:
        path.resolve().relative_to(INPUT_ROOT)
    return files


def package_inputs(output: Path = DEFAULT_OUTPUT) -> Path:
    """Write a ZIP containing verified input bytes and repository-relative paths."""
    files = input_files()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as target:
        try:
            with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
                for path, expected in files:
                    name = path.relative_to(ROOT).as_posix()
                    print(f"Packaging {name}", flush=True)
                    digest = hashlib.sha256()
                    with (
                        path.open("rb") as source,
                        archive.open(name, "w", force_zip64=True) as member,
                    ):
                        for chunk in iter(lambda: source.read(8 * 1024**2), b""):
                            digest.update(chunk)
                            member.write(chunk)
                    if digest.hexdigest() != expected:
                        raise ValueError(f"Input differs from the frozen comparison: {path}")
        except BaseException:
            output.unlink()
            raise
    return output


def main() -> None:
    """Build the minimal input archive without loading agent environments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = package_inputs(args.output)
    print(f"Created {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
