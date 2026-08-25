# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project

TissueAgent — a role-based multi-agent framework for spatial-transcriptomics
workflows. Python 3.12 backend (FastAPI + LangGraph) and a React/TypeScript
frontend. See `README.md` for the full overview and `INTEGRATING.md` for the
external-agent contract.

## Layout cheatsheet

- `src/agents/` — planner, recruiter, manager, evaluator, reporter, plus the
  agent registry for domain agents and external integrations.
- `src/graph/` — LangGraph workflow + state orchestration.
- `src/server/` — FastAPI backend (REST + WebSocket).
- `src/frontend/` — React/TypeScript UI (Vite dev server on port 5173).
- `src/config.py` — path constants and runtime settings; `DefaultModelCtor`
  is the global model knob.
- `knowledge/` — prompt-time source material (plan templates, skill snippets,
  API docs). Importable as a package.
- `workspace/` — runtime data root (`DATA_DIR`). `library/` is read-only to
  agents; `projects/<id>/outputs/` is the agent's working directory.
- `demo/`, `tests/`, `docs/` — notebooks, pytest suite, figures.

## Setup

The repo expects `uv` + Node 22 + Python 3.12. A Nix flake is provided
(`nix develop`). Direnv (`.envrc`) auto-activates the flake and `.venv`.

```bash
uv sync                     # python deps
cd src/frontend && npm install && cd ../..
```

At least one LLM key must be exported before running: `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`.

## Run

```bash
# Backend (dev, hot-reload)
PYTHONPATH=$(pwd)/src uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (dev, hot-reload, proxies API/WS to 8000)
cd src/frontend && npm run dev
```

Production single-process: `npm run build` then run uvicorn without
`--reload`; FastAPI serves the built React bundle. Headless notebooks live in
`demo/`.

## Test & lint

```bash
pytest tests/               # unit tests
ruff check .                # lint (config in pyproject.toml)
ruff format .               # formatter
```

Lint config: line length 100, Google docstring convention, rules `E,F,D`.
`**/prompt.py` is exempt from E501; `**/__init__.py`, `notebooks/**`, and
`**/deprecated/**` are skipped wholesale.

## Conventions

- Match the existing code style — don't reformat unrelated lines.
- Default to no comments. Only add one when the *why* is non-obvious.
- Don't introduce abstractions, fallbacks, or feature flags beyond what the
  task requires. Trust internal call sites; validate only at boundaries.
- Keep changes scoped. A bug fix shouldn't drag in refactors.
- Don't write to `workspace/library/` — agent file tools refuse it by design.
  Relative writes anchor to `workspace/projects/<active>/outputs/`.
- External-agent integrations follow the contract in `INTEGRATING.md`. The
  skeleton lives at `src/agents/agent_registry/_template_external_agent/`.
- Submodules: `src/agents/agent_registry/gene_agent/upstream/` is pinned via
  git submodule. Don't bump it casually.

## Commits & PRs

Only the repo owner commits and pushes. Never run `git commit`, `git push`,
`gh pr create`, or any destructive git operation — not even when asked to
"save" or "wrap up" work. Leave changes in the working tree and say what's
ready; the owner reviews and commits. Follow the existing concise commit style
(see `git log`) when drafting a message for them.
