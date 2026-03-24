# TissueAgent

## Repository set-up:

1. Clone the repository **with submodules** and `cd` into the local directory
   ```bash
   git clone --recurse-submodules https://github.com/ma-compbio/TissueAgent
   cd TissueAgent
   ```
   If you already cloned without `--recurse-submodules`, initialize them manually:
   ```bash
   git submodule update --init --recursive
   ```

2. Install Python 3.12 and [uv](https://docs.astral.sh/uv/)

3. Run `uv sync` in the local repository

### Usage (Web UI)

1. Run `source .venv/bin/activate` to activate the virtual environment created by `uv`

2. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function (e.g. `export OPENAI_API_KEY="sk-..."`). 

3. Use `PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py` to start the streamlit application from the base directory

4. Open the URL in a web browser

### Usage (Jupyter Notebook)

See `demo/` for examples on how to invoke TissueAgent directly from a Jupyter Notebook.

>[!TIP]
>All agents use GPT-5 by default. To save API tokens, models with lower reasonsing capabilities can be used. This can be configured globally by modifying `DefaultModelCtor` in `src/config.py` or changed on the subagent level by modifying `src/agents/agent_defns.py`.

### Long-term memory (Memori)

1. Install the optional dependency with `uv add memorisdk` (or `pip install memorisdk` in your active environment).

2. Configure the memory backend by setting environment variables before launching Streamlit, e.g.:
   ```bash
   export MEMORI_ENABLED=true
   export MEMORI_DATABASE_URL="sqlite:///$(pwd)/data/memori/memori.db"
   export MEMORI_USER_ID="..."
   export MEMORI_SESSION_ID="default"
   export MEMORI_OPENAI_API_KEY="s..."
   ```

3. When Memori is enabled the Streamlit sidebar shows the current status and every OpenAI chat completion issued by TissueAgent is intercepted and stored in the configured SQL database, giving the agents persistent long-term recall.

### Data Availability

All datasets referenced in the manuscript are publically available:
- Developing human heart MERFISH dataset (Farah et al., 2024): [https://cells.ucsc.edu/?ds=hoc](https://cells.ucsc.edu/?ds=hoc)
- 10x Visium human heart dataset (Kanemaru et al., 2023): [https://www.heartcellatlas.org/](https://www.heartcellatlas.org/)
- Single-cell reference dataset for cell type deconvolution: [CellxGene collection b52eb423](https://cellxgene.cziscience.com/collections/b52eb423-5d0d-4645-b217-e1c6d38b2e72)
- 10x Visium Alzheimer's disease spatial transcriptomics dataset (Miyoshi et al., 2024): GEO accession [GSE233208](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE233208)
- Spatial mouse atlas (Lohoff et al., 2022): [https://crukci.shinyapps.io/SpatialMouseAtlas/](https://crukci.shinyapps.io/SpatialMouseAtlas/)
- Spatiotemporal transcriptomics dataset (Chen et al., 2022): CNGBdb accession [STDS0000058](https://db.cngb.org/search/project/STDS0000058/)

### License

[MIT License](LICENSE)