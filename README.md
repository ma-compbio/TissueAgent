# TissueAgent

### Repository set-up:

1. Clone the repository and `cd` into the local directory

2. Install Python 3.12 and [uv](https://docs.astral.sh/uv/) (e.g. `pip` or `nix`):

3. Run `uv sync` in the local repository

4. Use `uv add [package]` to install additional dependencies through `pip`

### Usage

1. Run `source .venv/bin/activate` to activate the virtual environment created by `uv`

2. Export your LLM credentials. At minimum `OPENAI_API_KEY` must be set for the default agents to function (e.g. `export OPENAI_API_KEY="sk-..."`). 

3. Use `PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py` to start the streamlit application

### Long-term memory (Memori)

1. Install the optional dependency with `uv add memorisdk` (or `pip install memorisdk` in your active environment).
2. Configure the memory backend by setting environment variables before launching Streamlit, e.g.:
   ```bash
   export MEMORI_ENABLED=true
   export MEMORI_DATABASE_URL="sqlite:///$(pwd)/data/memori/memori.db"
   export MEMORI_USER_ID="wenduoc"
   export MEMORI_SESSION_ID="default"
   export MEMORI_OPENAI_API_KEY="s..."
   ```
3. When Memori is enabled the Streamlit sidebar shows the current status and every OpenAI chat completion issued by TissueAgent is intercepted and stored in the configured SQL database, giving the agents persistent long-term recall.

- All agents use GPT-5 as a default. Agents that don't require a lot of reasonsing capabilities can use a weaker LLM to save on API tokens.
