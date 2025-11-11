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


- `coding agent` often takes several tries to format responses correctly; prompt needs fine-tuning.
- `evaluator agent` does not support multi-modal input and does not inspect the contents of artifacts produced. Results in ill-formed artifacts, e.g. plots with the legend covering up most of the content.
- `gene agent` or `searcher agent` cannot generate expected files
- pdf understanding not tested
- (minor) Prompt format differs between agents (e.g. `planner agent` and `coding agent`)
- (minor) All agents use GPT-5 as a default. Agents that don't require a lot of reasonsing capabilities can use a weaker LLM to save on API tokens.
