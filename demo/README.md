

# Demo

This folder contains notebooks for several tasks described in the manuscript. Each notebook is self-contained and can be run end-to-end to load inputs, prompt the agent, and save outputs.

### Usage

1. Set up the repository (see [README.md](../README.md))

2. Run source `.venv/bin/activate` to activate the virtual environment created by `uv`

3. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function (e.g. `export OPENAI_API_KEY="sk-..."`).

4. Start a jupyter server with `jupyter notebook`.

5. Open a notebook and run it top-to-bottom to reproduce a task. Data can be accessed in `demo/data` and outputs are written to `data/` and copied into `demo/outputs/{TASK}`. The run is logged to `demo/outputs/{TASK}/transcript.log`.

> [!WARNING]
> LLM outputs are inherently stochastic, so TissueAgent may produce slightly different outputs between runs. 

### Structure
```
demo
├── data/                                # datasets and inputs for demo tasks
├── outputs/                             # transcripts and artifacts from demo tasks
├── figure_recreation_lohoff-2b.ipynb    # notebook for figure recreation task (Figure 2b from Lohoff et. al.)
├── figure_recreation_lohoff-2e.ipynb    # notebook for figure recreation task (Figure 2c from Lohoff et. al.)
├── notebook_utils.py                    # utility functions for setting up and running TissueAgent in notebooks
└── README.md
```

### Web UI Demo

https://github.com/user-attachments/assets/581aca67-abda-40bd-a698-3a5242d06d66

