# `_template_external_agent` (do not edit in place)

This folder is a skeleton for new external-agent integrations. To create
a new agent:

1. **Copy** the entire folder to a sibling under `agent_registry/`,
   renaming it to your agent's snake_case id (e.g. `my_agent`).
2. **Fill in** `manifest.yaml` (id, name, version, upstream pin,
   required env vars).
3. **Add the upstream code** as a git submodule under `upstream/`:
   ```bash
   git submodule add <repo-url> src/agents/agent_registry/<my_agent>/upstream
   ```
4. **Write** `prompt.py`, `tool.py`, and `runner.py`.
5. **Uncomment** the imports and `agent_definition` assignment in
   `__init__.py`.
6. **Register** in `src/agents/agent_defns.py` by adding a `ReActAgent`
   entry that delegates to your `agent_definition`.

See:
- `INTEGRATING.md` at the repository root for the full recipe.
- `agent_registry/gene_agent/` for a worked example.

The leading underscore in the folder name keeps Python from importing
this template at runtime.
