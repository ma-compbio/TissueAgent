# TISSUEAGENT: A Role-Based Multi-Agent Framework for Reproducible Spatial Transcriptomics Workflows

## Project Overview

TISSUEAGENT is a role-based multi-agent framework that turns open-ended natural-language ST requests and multimodal inputs (data, PDFs, images) into auditable, runnable workflows. A single evolving plan coordinates specialized agents and records rationales, step status, and artifact links, enabling transparent provenance and targeted replanning. By separating planning, recruitment, execution, evaluation, and reporting, TISSUEAGENT is designed to improve reliability across heterogeneous, multi-stage analyses.

## Key Features

- Role-based multi-agent design with explicit separation of planning, recruitment, execution, evaluation, and reporting.
- A single evolving plan that tracks rationales, step status, and artifact links to support transparent provenance and targeted replanning.
- Built-in collaboration with external specialized agents to extend capabilities for domain-specific tasks.
- Support for diverse spatial transcriptomics workflows such as figure reproduction, cell type annotation, cell-cell communication, differential gene expression, and cell type deconvolution.

![TISSUEAGENT overview figure](docs/figures/tissueagent_overall_design.png)

## Repository set-up

1. Clone the repository **with submodules** and `cd` into the local directory
   ```bash
   git clone --recurse-submodules https://github.com/ma-compbio/TissueAgent
   cd TissueAgent
   ```
   If you already cloned without `--recurse-submodules`, initialize them manually:
   ```bash
   git submodule update --init --recursive
   ```

2. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

### Option A: Using Nix (recommended)

A `flake.nix` is provided that supplies Python 3.12, uv, Node.js 22, and npm.

1. [Install Nix](https://nixos.org/download) if you haven't already.

2. Enter the dev shell and install dependencies:
   ```bash
   nix develop          # drops you into a shell with python, uv, node, npm
   uv sync              # creates .venv and installs Python deps
   cd src/frontend
   npm install           # installs React/TypeScript deps
   cd ../..
   ```

3. Start the application (two terminals, both inside `nix develop`):
   ```bash
   # Terminal 1 — FastAPI backend
   source .venv/bin/activate
   PYTHONPATH=$(pwd)/src uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

   # Terminal 2 — React dev server (hot-reload)
   cd src/frontend
   npm run dev
   ```

4. Open **http://localhost:5173** in a web browser. The React dev server proxies API and WebSocket requests to the FastAPI backend automatically.

#### Production mode (single process)

```bash
nix develop
source .venv/bin/activate
cd src/frontend && npm run build && cd ../..
PYTHONPATH=$(pwd)/src uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Open **http://localhost:8000**. FastAPI serves the built React app as static files.

### Option B: Without Nix

You will need to install the following manually:
- **Python 3.12** — [python.org](https://www.python.org/downloads/) or your system package manager
- **uv** — [docs.astral.sh/uv](https://docs.astral.sh/uv/)
- **Node.js 22+** and **npm** — [nodejs.org](https://nodejs.org/)

1. Install dependencies:
   ```bash
   uv sync              # creates .venv and installs Python deps
   cd src/frontend
   npm install           # installs React/TypeScript deps
   cd ../..
   ```

2. Start the application (two terminals):
   ```bash
   # Terminal 1 — FastAPI backend
   source .venv/bin/activate
   PYTHONPATH=$(pwd)/src uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

   # Terminal 2 — React dev server (hot-reload)
   cd src/frontend
   npm run dev
   ```

3. Open **http://localhost:5173** in a web browser.

#### Production mode (single process)

```bash
source .venv/bin/activate
cd src/frontend && npm run build && cd ../..
PYTHONPATH=$(pwd)/src uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Open **http://localhost:8000**.

### Option C (Headless Mode)

Install uv, Python 3.12, and run `uv sync` from the root of this repository to install all Python packages. Then, see `demo/` for examples on how to invoke TissueAgent directly from a Jupyter Notebook.

> [!TIP]
> All agents use GPT-5 by default. To save API tokens, models with lower reasoning capabilities can be used. This can be configured globally by modifying `DefaultModelCtor` in `src/config.py` or changed on the subagent level by modifying `src/agents/agent_defns.py`.

## Data Availability

All datasets referenced in the manuscript are publicly available:
- Developing human heart MERFISH dataset (Farah et al., 2024): [https://cells.ucsc.edu/?ds=hoc](https://cells.ucsc.edu/?ds=hoc)
- 10x Visium human heart dataset (Kanemaru et al., 2023): [https://www.heartcellatlas.org/](https://www.heartcellatlas.org/)
- Single-cell reference dataset for cell type deconvolution: [CellxGene collection b52eb423](https://cellxgene.cziscience.com/collections/b52eb423-5d0d-4645-b217-e1c6d38b2e72)
- 10x Visium Alzheimer's disease spatial transcriptomics dataset (Miyoshi et al., 2024): GEO accession [GSE233208](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE233208)
- Spatial mouse atlas (Lohoff et al., 2022): [https://crukci.shinyapps.io/SpatialMouseAtlas/](https://crukci.shinyapps.io/SpatialMouseAtlas/)
- Spatiotemporal transcriptomics dataset (Chen et al., 2022): CNGBdb accession [STDS0000058](https://db.cngb.org/search/project/STDS0000058/)

### License

[MIT License](LICENSE)
