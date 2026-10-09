

# Demo

This folder contains notebooks for several tasks described in the manuscript. Each notebook is self-contained and can be run end-to-end to load inputs, prompt the agent, and save outputs.

### Usage

1. Set up the repository (see [README.md](../README.md))

2. Run source `.venv/bin/activate` to activate the virtual environment created by `uv`

3. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function (e.g. `export OPENAI_API_KEY="sk-..."`).

4. Start a jupyter server with `jupyter notebook`.

5. Open a notebook and run it top-to-bottom to reproduce a task. Data can be accessed in `demo/data` and outputs are written to `workspace/` and copied into `demo/outputs/{TASK}`. The run is logged to `demo/outputs/{TASK}/transcript.log`.

> [!WARNING]
> LLM outputs are inherently stochastic, so TissueAgent may produce slightly different outputs between runs. 

### Structure
```
demo
├── data/                                # datasets and inputs for demo tasks
├── outputs/                             # transcripts and artifacts from demo tasks
├── figure_recreation_lohoff-2a.ipynb    # atlas and seqFISH joint UMAP figure reproduction
├── figure_recreation_lohoff-2b.ipynb    # notebook for figure recreation task (Figure 2b from Lohoff et. al.)
├── figure_recreation_lohoff-2e.ipynb    # notebook for figure recreation task (Figure 2c from Lohoff et. al.)
├── spot_deconvolution_visium_heart.ipynb    # notebook for cell-type deconvolution task
├── notebook_utils.py                    # utility functions for setting up and running TissueAgent in notebooks
└── README.md
```

### Lohoff Figure 2a: atlas and seqFISH

[`figure_recreation_lohoff-2a.ipynb`](figure_recreation_lohoff-2a.ipynb) supplies both `data/gastrulation_atlas_joint_umap.csv` and `data/seqfish_author_joint_umap.csv`. These contain the authors' published joint UMAP coordinates and cell-type labels from [`MGA_joint_UMAP.Rds`](https://content.cruk.cam.ac.uk/jmlab/SpatialMouseAtlas2020/MGA_joint_UMAP.Rds). The original seqFISH AnnData is also supplied, but its different embedding is not combined with the atlas coordinates. Source information and checksums are in `data/provenance_lohoff-2a.json`.

This demo reconstructs the plotting workflow from processed coordinates; it does not recompute integration, cell-type annotation, or UMAP from expression. No palette file is supplied. The completed figure contains 16,861 atlas cells and 52,568 seqFISH cells after excluding 4,968 cells labeled `Low quality`.

The notebook includes the completed [result](outputs/figure_recreation_lohoff-2a_with_atlas/figures/lohoff_fig2a_recreated.png), copied from the [atlas benchmark run](../benchmark/lohoff_2a_with_atlas_20261005/README.md), with its transcript, metrics, reports, and plotting code. It reuses that result only when the prompt, model, and input checksums match. To launch a fresh run, choose a new `OUTPUT_DIR` in the notebook and configure `OPENAI_API_KEY`. The previous seqFISH-only outputs remain in `outputs/figure_recreation_lohoff-2a/`.

### Hypothesis-recovery benchmark (Comment #7)

See [`benchmark/hypothesis_recovery/README.md`](../benchmark/hypothesis_recovery/README.md) and
[`METHODS.md`](../benchmark/hypothesis_recovery/METHODS.md). Quick start:

```bash
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm tissueagent --seed-existing
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm cellvoyager --num-analyses 1 --model gpt-4o
PYTHONPATH=src python demo/score_hypothesis_recovery.py --all --aggregate
```

### Web UI Demo

https://github.com/user-attachments/assets/ef381418-cf5c-431b-9052-f931c922d2c8
