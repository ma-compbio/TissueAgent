# Demo

This folder contains notebooks for several tasks described in the manuscript. Each notebook is self-contained and can be run end-to-end to load inputs, prompt the agent, and save outputs.

### Usage

1. Set up the repository (see [README.md](../README.md))

2. Run source `.venv/bin/activate` to activate the virtual environment created by `uv`

3. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function (e.g. `export OPENAI_API_KEY="sk-..."`).

4. Start a jupyter server with `jupyter notebook`.

5. Open a notebook and run it top-to-bottom to reproduce a task. Data can be accessed in `demo/data`; generated data is written under `data/`, and reviewer artifacts are written under `demo/outputs/`.

### Cell annotation benchmark

Use `cell_annotation_benchmark.ipynb` for the reviewer benchmark. Its controls select one of the developing human heart, mouse CNS, or ovarian cancer datasets, quick/full execution, and any combination of TissueAgent, CellTypist, and GPTCellType.

- Heart uses the existing local H5AD and local reference without downloading or reconversion.
- Mouse CNS is converted from the required Zenodo raw-expression, spatial, metadata, and cluster CSVs in `scratch/zenodo_8327576_csv`; processed-expression and molecule-level spot files are not read.
- Ovarian cancer uses the local `ST_Test1_so.rds` and the controlled Seurat conversion bridge.
- Ground truth is saved separately before annotation. Missing or unmapped predictions are scored as `Unassigned` rather than dropped.
- Before Harmony transfer, TissueAgent inspects bounded samples from both AnnData expression matrices and makes an evidence-backed preprocessing decision. Ambiguous or incompatible matrix states stop visibly rather than using a dataset-specific hard-coded flag.
- The notebook does not install packages, display credentials, or delete shared datasets/results.

`cell_annotation_w_baselines.ipynb` is retained as a legacy development record; it is not the canonical three-dataset workflow.

The completed all-cell TissueAgent evaluation is summarized in
[`outputs/cell_annotation/full-20260711_summary.md`](outputs/cell_annotation/full-20260711_summary.md).
The earlier 25,000-cell comparison remains at
[`outputs/cell_annotation/quick-20260711_summary.md`](outputs/cell_annotation/quick-20260711_summary.md),
with its superseded heart preprocessing configuration called out explicitly.
Each dataset run directory contains the method predictions, metrics, confusion matrices,
unmapped-label audit, tool metadata, and complete TissueAgent transcript.


> [!WARNING]
> LLM outputs are inherently stochastic, so TissueAgent may produce slightly different outputs between runs. 

### Structure
```
demo
├── data/                                # datasets and inputs for demo tasks
├── outputs/                             # transcripts and artifacts from demo tasks
├── figure_recreation_lohoff-2b.ipynb    # notebook for figure recreation task (Figure 2b from Lohoff et. al.)
├── figure_recreation_lohoff-2e.ipynb    # notebook for figure recreation task (Figure 2c from Lohoff et. al.)
├── cell_annotation_benchmark.ipynb      # canonical three-dataset cell annotation benchmark
├── cell_annotation/                     # manifests, direct baselines, metrics, and runners
├── notebook_utils.py                    # utility functions for setting up and running TissueAgent in notebooks
└── README.md
```
