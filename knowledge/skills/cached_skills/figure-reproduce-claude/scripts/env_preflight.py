#!/usr/bin/env python3
"""Environment preflight for the 'figure-reproduce' skill.

WHAT THIS DOES
--------------
Reports whether the current runtime is capable of reproducing scientific
figures, and — for anything that is missing — prints a one-line install hint.
This is the "environment" step of the figure-reproduce skill: a *report*, not
a gate. It does NOT install anything and has no side effects on disk.

It inspects:
  * Python version + interpreter path
  * Rscript on PATH (for R-based figure code) + its version
  * Key Python libraries, grouped by role:
      - CORE plotting        : numpy, pandas, matplotlib   (the must-haves)
      - extended plotting     : seaborn
      - omics (OPTIONAL)      : scanpy, anndata, squidpy    (domain-specific)
      - image / compare       : Pillow, scikit-image, opencv-python (cv2), imagehash
      - io                    : openpyxl, pyarrow, h5py
      - pdf                   : PyMuPDF (fitz)

USAGE
-----
    python env_preflight.py            # human-readable report
    python env_preflight.py --json     # machine-readable JSON report
    python env_preflight.py --strict   # exit non-zero if CORE stack is missing

Portable: a single self-contained Python 3 file, stdlib-only for its own
operation. It imports third-party libraries only to *probe* them, and every
such probe is wrapped so a missing dependency degrades to a warning rather
than a traceback. Safe to copy to any host.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata as md
import json
import shutil
import subprocess
import sys

# --- Library catalog -------------------------------------------------------
# Each entry: (import_name, distribution_name, one-line install hint).
# import_name  = what `import X` uses (may differ from the pip package).
# dist_name    = the PyPI distribution, used for version lookup + the hint.
# The hint may mention conda / Rscript alternatives where relevant.
GROUPS: dict[str, dict] = {
    "core_plotting": {
        "label": "CORE plotting",
        "optional": False,
        "libs": [
            ("numpy", "numpy", "pip install numpy"),
            ("pandas", "pandas", "pip install pandas"),
            ("matplotlib", "matplotlib", "pip install matplotlib"),
        ],
    },
    "extended_plotting": {
        "label": "extended plotting",
        "optional": True,
        "libs": [
            ("seaborn", "seaborn", "pip install seaborn"),
        ],
    },
    "omics": {
        "label": "omics (OPTIONAL / domain-specific)",
        "optional": True,
        "libs": [
            ("scanpy", "scanpy", "pip install scanpy  (or: conda install -c conda-forge scanpy)"),
            ("anndata", "anndata", "pip install anndata"),
            ("squidpy", "squidpy", "pip install squidpy  (spatial omics; heavy deps)"),
        ],
    },
    "image_compare": {
        "label": "image / compare",
        "optional": True,
        "libs": [
            ("PIL", "Pillow", "pip install Pillow"),
            ("skimage", "scikit-image", "pip install scikit-image"),
            ("cv2", "opencv-python", "pip install opencv-python  (or: opencv-python-headless on servers)"),
            ("imagehash", "ImageHash", "pip install ImageHash"),
        ],
    },
    "io": {
        "label": "io (spreadsheets / columnar / HDF5)",
        "optional": True,
        "libs": [
            ("openpyxl", "openpyxl", "pip install openpyxl"),
            ("pyarrow", "pyarrow", "pip install pyarrow"),
            ("h5py", "h5py", "pip install h5py"),
        ],
    },
    "pdf": {
        "label": "pdf",
        "optional": True,
        "libs": [
            ("fitz", "PyMuPDF", "pip install PyMuPDF  (imported as 'fitz')"),
        ],
    },
}


def _probe_library(import_name: str, dist_name: str) -> dict:
    """Return {present, version, error} for one library, never raising.

    We try to import the module (authoritative proof it is usable) and, whether
    or not that succeeds, try to read the installed distribution's version via
    importlib.metadata so we can report a version without importing heavy deps.
    """
    result = {"present": False, "version": None, "error": None}

    # Version from package metadata (cheap, no side effects).
    try:
        result["version"] = md.version(dist_name)
    except md.PackageNotFoundError:
        result["version"] = None
    except Exception:  # pragma: no cover - defensive, metadata quirks
        result["version"] = None

    # Authoritative import check — wrapped so a broken/absent dep never crashes us.
    try:
        importlib.import_module(import_name)
        result["present"] = True
        if result["version"] is None:
            # Fall back to a module __version__ attribute if metadata missed it.
            mod = sys.modules.get(import_name)
            result["version"] = getattr(mod, "__version__", None)
    except Exception as exc:  # ImportError, or a heavy module failing at import
        result["present"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def _probe_rscript() -> dict:
    """Locate Rscript and capture its version, without raising."""
    path = shutil.which("Rscript")
    info = {"present": path is not None, "path": path, "version": None}
    if not path:
        return info
    try:
        # Rscript prints its version banner to stderr.
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        info["version"] = (proc.stderr or proc.stdout).strip() or None
    except Exception as exc:  # timeout, permission, exotic R build
        info["version"] = f"(could not read version: {type(exc).__name__})"
    return info


def build_report() -> dict:
    """Assemble the full structured report dict."""
    groups_report: dict[str, dict] = {}
    for key, spec in GROUPS.items():
        libs = {}
        for import_name, dist_name, hint in spec["libs"]:
            probe = _probe_library(import_name, dist_name)
            probe["import_name"] = import_name
            probe["dist"] = dist_name
            probe["hint"] = hint
            libs[dist_name] = probe
        groups_report[key] = {
            "label": spec["label"],
            "optional": spec["optional"],
            "libs": libs,
        }

    core = groups_report["core_plotting"]["libs"]
    core_ok = all(core[d]["present"] for d in core)

    return {
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "rscript": _probe_rscript(),
        "groups": groups_report,
        "core_stack_present": core_ok,
    }


def _fmt_lib_line(probe: dict) -> str:
    """One aligned status line for a single library."""
    mark = "ok " if probe["present"] else "MISSING"
    ver = probe["version"] or ("-" if not probe["present"] else "?")
    return f"    [{mark}] {probe['dist']:<16} {ver}"


def print_human(report: dict) -> None:
    """Render the report for a human reader."""
    py = report["python"]
    print("Figure-reproduce environment preflight")
    print("=" * 46)
    print(f"Python : {py['version']}  ({py['executable']})")

    r = report["rscript"]
    if r["present"]:
        print(f"Rscript: found at {r['path']}")
        if r["version"]:
            print(f"         {r['version'].splitlines()[0]}")
    else:
        print("Rscript: not found on PATH  (install R if any figure code is R-based)")

    missing_hints: list[str] = []
    for spec in report["groups"].values():
        opt = "  (optional)" if spec["optional"] else "  (required)"
        print(f"\n{spec['label']}{opt}")
        for probe in spec["libs"].values():
            print(_fmt_lib_line(probe))
            if not probe["present"]:
                missing_hints.append(f"    - {probe['dist']}: {probe['hint']}")

    if missing_hints:
        print("\nInstall hints for missing libraries:")
        for line in missing_hints:
            print(line)

    print("\n" + "-" * 46)
    if report["core_stack_present"]:
        print("VERDICT: CORE plotting stack (numpy+pandas+matplotlib) is PRESENT.")
    else:
        print("VERDICT: CORE plotting stack (numpy+pandas+matplotlib) is INCOMPLETE.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report figure-reproduction runtime capabilities and install hints "
        "(part of the 'figure-reproduce' skill). Reports only; installs nothing.",
    )
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if the CORE plotting stack is missing",
    )
    args = parser.parse_args(argv)

    report = build_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)

    # This is a report, not a gate: exit 0 unless --strict and core is missing.
    if args.strict and not report["core_stack_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
