# TissueAgent

### Repository set-up:

1. Clone the repository and `cd` into the local directory

2. Install Python 3.12 and [uv](https://docs.astral.sh/uv/) (e.g. `pip` or `nix`):

3. Run `uv sync` in the local repository

4. Use `uv add [package]` to install additional dependencies through `pip`

### Usage

1. Run `source .venv/bin/activate` to activate the virtual environment created by `uv`

2. Use `PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py` to start the streamlit application