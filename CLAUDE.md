# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TissueAgent is a role-based multi-agent framework for spatial-transcriptomics workflows. A LangGraph state graph drives a 5-stage pipeline of "main" agents that recruit and dispatch specialized sub-agents. The system is delivered as a FastAPI backend + React/TypeScript frontend, and is also usable headless from Jupyter notebooks (see `demo/`).

## Environment & common commands

Python 3.12 + Node 22. Three supported toolchains — all install the same `pyproject.toml` deps:

- **uv:** `uv sync` (creates `.venv/`); activate with `source .venv/bin/activate`.
- **conda:** `conda env create -f environment.yml && conda activate tissueagent && pip install -e .`
- **nix:** `nix develop` then `uv sync`.

The frontend is a separate npm project: `cd src/frontend && npm install`.

After cloning, initialize the GeneAgent git submodule: `git submodule update --init --recursive` (path: `src/agents/agent_registry/gene_agent/original_repo/GeneAgent`).

Set `OPENAI_API_KEY` before starting anything — the default `DefaultModelCtor` in `src/config.py` is `ChatOpenAI(model="gpt-5", reasoning_effort="high")` and the graph will not build without a valid key.

Run the stack (two terminals):

```bash
# backend — note the PYTHONPATH; uvicorn must see src/ as the module root
PYTHONPATH=$(pwd)/src uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# frontend (dev mode w/ HMR, proxies /api and /ws to :8000)
cd src/frontend && npm run dev    # http://localhost:5173
```

Production (single process, FastAPI serves the built React app from `src/frontend/dist`):
```bash
cd src/frontend && npm run build && cd ../..
PYTHONPATH=$(pwd)/src uvicorn server.main:app --host 0.0.0.0 --port 8000   # http://localhost:8000
```

Headless / notebook usage: skip the frontend entirely and run notebooks in `demo/` (e.g. `demo/figure_recreation_lohoff-2b.ipynb`, `demo/spot_deconvolution_visium_heart.ipynb`).

Linting:
- Python: `ruff check .` (config in `pyproject.toml` — 120-col line length, Google docstrings, `select = ["E","F","D"]`). Notebooks, `__init__.py`, and `**/deprecated/**` are ignored.
- Frontend: `cd src/frontend && npm run lint`.
- Tests: there is no test suite in this repo; verify changes by running a notebook or driving the web UI.

## Architecture

### Main pipeline (LangGraph)

`src/graph/graph.py::create_tissueagent_graph` wires a `StateGraph(MessagesState)` with five main agents, each as an `agent_node` + `tool_node` pair created by `src/graph/graph_utils.py`:

```
START → Planner → (Recruiter → Manager → Evaluator) → Reporter → END
                       ↑__________________│
                          replan (≤ MAX_REPLANS=2)
```

- **Planner** (`src/agents/planner_agent/`) — builds/refines a single evolving plan. Can short-circuit the pipeline by emitting `ROUTE: DIRECT` or `ROUTE: CLARIFY` as the first line of its response (handled in `planner_router`). YAML plan templates live in `planner_agent/plan_registry/`.
- **Recruiter** (`src/agents/recruiter_agent/`) — selects specialized agents for the plan. Its prompt is a callable that takes the `agent_id_descriptions` dict (see below).
- **Manager** (`src/agents/manager_agent/`) — executes plan steps. Its tool set is `ManagerTool + agent_invocation_tools`: every specialized sub-agent is wrapped via `create_agent_invocation_tool` and exposed to the Manager as a callable tool. Manager prompt is also `agent_id_descriptions`-aware.
- **Evaluator** (`src/agents/evaluator_agent/`) — decides `ROUTE: REPLAN` (goes back to Planner) or `ROUTE: REPORT` (forward to Reporter). `evaluator_state_update` tracks `replan_count`; on the 3rd replan it rewrites the response to `ROUTE: REPORT` so the graph terminates cleanly.
- **Reporter** (`src/agents/reporter_agent/`) — writes the final artifact (Jupyter notebook via `reporter_agent/tools_impl/jupyternb_generator_tool.py`).

`RECURSION_LIMIT = 100` is set in `src/config.py` and is passed to the compiled graph at runtime.

### Specialized sub-agents

All declared in `src/agents/agent_defns.py` as a single `AgentDefns` list. Two flavors:

- **`ReActAgent`** — standard agent-node/tool-node ReAct loop. Compiled into a sub-graph and wrapped as a Manager tool via `create_agent_invocation_tool`. Two flags handled inline in `graph.py`: `supports_pdf=True` for `pdf_reader`, `forward_user_images=True` for `coding`.
- **`CustomAgent`** — provides its own `ctor(state_queue) -> StructuredTool`, used when the sub-graph topology is non-standard. Currently: `coding` (CodeAct-style loop in `agent_registry/coding_agent/model.py`) and `hypothesis`.

Current sub-agents: `coding`, `pdf_reader`, `searcher`, `single_cell`, `critic`, `gene_agent`, `cell_annotater`, `spot`, `hypothesis`. Each lives in `src/agents/agent_registry/<name>/` with `prompt.py` + `tools.py` (and often `tools_impl/`).

When adding a new sub-agent: define it in `agent_registry/<name>/`, import it in `agent_defns.py`, and append to `AgentDefns`. The Manager automatically gets a tool for it; the Recruiter prompt automatically sees its description through the `agent_id_descriptions` map built in `graph.py`.

### Model configuration

`DefaultModelCtor` in `src/config.py` is the *global* default model for every agent. To change models per-agent, edit `model_ctor=` on the relevant entry in `src/agents/agent_defns.py`. Models are wrapped with `_bind_retry` in `src/server/main.py` (retries `openai.RateLimitError` / `anthropic.RateLimitError` up to 6 times).

### Server, sessions, and state plumbing

- `src/server/main.py` is the FastAPI entry-point. `lifespan()` calls `reset_data_directories()`, registers the UI event queue, compiles the graph, and stores it on `session.agent`. **Heads-up:** `reset_data_directories()` wipes `data/dataset`, `data/uploads`, `data/pdfs`, and the entire `sessions/` directory on every backend start — do not leave anything important under `data/` between runs.
- Routes: `src/server/routes/{chat,files,sessions}.py`. Real-time updates flow through a thread-safe `state_queue` populated by `create_agent_invocation_tool` and consumed over WebSocket.
- `src/server/session_manager.py` holds the singleton `session` (agent, queues).

Runtime directories (defined in `src/config.py`): `data/dataset`, `data/uploads`, `data/pdfs`, `data/notebook`, `sessions/`, `logs/`. All are under the repo root, not under `src/`.

### Frontend

Vite + React 19 + TypeScript in `src/frontend/`. Dev server proxies `/api` → `:8000` and `/ws` → `ws://:8000` (see `vite.config.ts`). Production build (`dist/`) is mounted as static files by FastAPI when present.

## Conventions worth knowing

- `src/` is the module root — always run Python with `PYTHONPATH=$(pwd)/src` (or from inside `src/`). Imports like `from agents.x import y` and `from graph.graph import ...` rely on this.
- Prompt files are exempt from ruff's `E501` line-length rule (`pyproject.toml`'s `[tool.ruff.lint.per-file-ignores]`). It is fine for prompts to be long lines.
- Routing between main agents is decided by the **first line** of the LLM's response (`ROUTE: DIRECT|CLARIFY|REPLAN|REPORT`). Preserve this contract when editing the corresponding prompts.
- Logging is set up at import time by `src/logger.py`; `LOG_TO_FILE` is computed from a timestamp in `src/config.py`, so each backend run gets a fresh `logs/<timestamp>_tissueagent.log`.
