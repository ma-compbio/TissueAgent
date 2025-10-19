# TissueAgent

### Repository set-up:

1. Clone the repository and `cd` into the local directory

2. Install Python 3.12 and [uv](https://docs.astral.sh/uv/) (e.g. `pip` or `nix`):

3. Run `uv sync` in the local repository

4. Use `uv add [package]` to install additional dependencies through `pip`

### Usage

1. Run `source .venv/bin/activate` to activate the virtual environment created by `uv`

2. Use `PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py` to start the streamlit application

### Known Issues

- Agent and Tool outputs from `coding agent` are not displayed to streamlit UI
- `coding agent` often takes several tries to format responses correctly; prompt needs fine-tuning.
- Agent workflow not being rendered properly on streamlit. Results in this error:
```
2025-10-19 16:33:18 | ERROR    | No agent state found for following message content='Success: notebook successfully exported to notebooks/spatial_scatter_repro.ipynb' name='jupyternb_generator_tool' id='ef72bdf4-066b-4d40-a422-017b43768e5a' tool_call_id='call_CW7XaUpcZeU0EcpVNeENtyI5'
```
- Agents write folder to `TissueAgent/` directory instead of `data/` subdirectory
- Plan and subsequent revisions are not being displayed explicitely to streamlit UI
- `jupyternb_generator_tool` produces empty notebooks
- Lots of deprecated or unused code left in the code base
- `evaluator agent` does not support multi-modal input and does not inspect the contents of artifacts produced. Results in ill-formed artifacts, e.g. plots with the legend covering up most of the content.
- (minor) Prompt format differs between agents (e.g. `planner agent` and `coding agent`)
- (minor) All agents use GPT-5 as a default. Agents that don't require a lot of reasonsing capabilities can use a weaker LLM to save on API tokens.