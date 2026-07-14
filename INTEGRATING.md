# Integrating an external agent

TissueAgent treats *external agents* — third-party research codebases
adapted into the framework — as first-class extension points. This guide
documents the formal contract and the recipe for adding a new one.

## Worked example

The canonical reference integration is **`src/agents/agent_registry/gene_agent/`**,
which wraps [NCBI's GeneAgent](https://github.com/ncbi-nlp/GeneAgent).
Read it alongside this document — every file mentioned below has a
concrete counterpart there.

## File structure

Every external agent lives in its own folder under
`src/agents/agent_registry/<agent_id>/` with the following layout:

```
<agent_id>/
├── manifest.yaml      Declarative metadata (id, version, upstream pin, env vars)
├── README.md          What the adapter does, what credentials it needs
├── __init__.py        Exports `agent_definition: ExternalAgentDefinition`
├── prompt.py          Description + system prompt shown to the recruiter/manager
├── tool.py            One or more StructuredTools the manager invokes
├── runner.py          The Python adapter that calls the upstream code
└── upstream/          Git submodule pinned to the tested upstream commit
```

A skeleton matching this layout is provided at
`src/agents/agent_registry/_template_external_agent/`. Copy it, rename
the folder to your agent's snake_case id, and fill in each file.

## Step-by-step recipe

### 1. Choose an id

Pick a stable lowercase snake_case identifier (e.g. `gene_agent`,
`pathway_finder`). It must be globally unique within
`agent_registry/`, will appear in URLs and logs, and **cannot be
renamed easily**.

### 2. Copy the template

```bash
cp -r src/agents/agent_registry/_template_external_agent \
      src/agents/agent_registry/<agent_id>
```

### 3. Add the upstream code as a submodule

```bash
git submodule add <repo-url> \
    src/agents/agent_registry/<agent_id>/upstream
cd src/agents/agent_registry/<agent_id>/upstream
git checkout <tested-commit>
cd -
```

Record the commit SHA in `manifest.yaml` (`upstream.commit`). When you
later upgrade, you bump this and re-test.

### 4. Fill in `manifest.yaml`

```yaml
id: <agent_id>
name: My Agent                # human-readable
version: 0.1.0                # semver for the adapter, not the upstream

upstream:
  repo: <repo-url>
  commit: <tested-commit>

llm:
  pinned_model: gpt-5.1       # OR omit to follow TissueAgent's UI selection
  required_env_vars:
    - OPENAI_API_KEY

data_subdir: <agent_id>

tool:
  name: <agent_id>_run_tool
  description: >
    One-sentence description for the manager.
```

The `llm.pinned_model` field is the critical knob:

- **Pin to a specific model** when the upstream agent's published results
  depend on a particular model (e.g. GeneAgent's published cascade was
  evaluated against GPT-4 / GPT-5; we pin to `gpt-5.1` for
  reproducibility).
- **Omit** to follow whatever the user has selected for the *Expert*
  agents in TissueAgent's UI.

### 5. Write `prompt.py`

Two top-level strings:

- `<Name>Description` — 1–3 sentences. Read by the recruiter to decide
  when to invoke. Be explicit about input/output contract and scope.
- `<Name>Prompt` — full system prompt. Use the gene_agent prompt as a
  template; the standard structure is:
  - **Visibility & Channels** (which tags are internal vs user-facing)
  - **Tool list** with arguments and return shapes
  - **Pre-flight checks** (validate inputs before calling the tool)
  - **Post-flight checks** (extract evidence, list artifacts)
  - **Output format** (worked example wrapped in `<final>…</final>`)

### 6. Write `runner.py`

This is where the real work happens. Two common patterns:

#### Pattern A — legacy openai==0.28 upstream

Most published research code falls here. Use
`agents.llm_compat.patch_openai_legacy_api(pinned_model=...)` to
monkey-patch the modern `openai` module so the legacy
`openai.ChatCompletion.create(...)` calls keep working, and so the
model is pinned regardless of what the upstream's hard-coded `engine=`
or `model=` arguments say.

See `agent_registry/gene_agent/runner.py` for the full pattern: import
the upstream module inside the `patch_openai_legacy_api` context,
run it inside a per-request working directory, and parse its outputs
into a JSON-serialisable dict.

#### Pattern B — modern upstream

If the upstream already uses `openai>=1.0` (or has its own LangChain
wiring), just import and call it. You may still want to set the
working directory and gather artifacts the same way.

### 7. Write `tool.py`

Wrap your runner function in a `StructuredTool`:

```python
from langchain.tools import StructuredTool
from .runner import run_my_agent

MyAgentTools = [
    StructuredTool.from_function(
        func=run_my_agent,
        name="<agent_id>_run_tool",
        description="…",
    )
]
```

LangChain auto-derives the JSON schema from your function's type hints,
so use concrete primitive types (`list[str]`, `str`, etc.) in the
signature — avoid `Any`.

### 8. Wire `__init__.py`

Uncomment and fill in the `agent_definition` block. This is the single
symbol the rest of TissueAgent will import.

### 9. Register in `agent_defns.py`

```python
from agents.agent_registry.<agent_id> import agent_definition as MyAgentDef

AgentDefns = [
    ...,
    ReActAgent(
        id=MyAgentDef.id,
        name=MyAgentDef.name,
        description=MyAgentDef.description,
        prompt=MyAgentDef.prompt,
        tools=MyAgentDef.tools,
        model_ctor=MyAgentDef.model_ctor,
    ),
]
```

### 10. Test

Confirm that the agent loads, runs end-to-end against a small input, and
writes artifacts to `data/<data_subdir>/<request_id>/`. Document any
required credentials in your `README.md`.

## LLM compatibility cheat sheet

| Upstream calls | TissueAgent runtime | Use |
|---|---|---|
| `openai.ChatCompletion.create(...)` (legacy 0.28) | openai>=1.73 | `patch_openai_legacy_api(pinned_model=...)` |
| `OpenAI().chat.completions.create(...)` (modern) | openai>=1.73 | call directly; pass `api_key=get_api_key("openai")` |
| Anthropic / Claude native | LangChain | use TissueAgent's `model_ctor_for_role("worker")` |
| Custom HTTP API | — | route through your own client; consult `models.get_api_key(...)` |

## Using Claude Code or Codex CLI to scaffold a new agent

If you'd like AI assistance building the adapter, the recommended
workflow is **one-shot scaffold generation**, not runtime delegation:

1. Open a Claude Code or Codex CLI session in the repo root.
2. Point it at this `INTEGRATING.md` and the `_template_external_agent/`
   skeleton.
3. Provide the upstream repo URL and a one-paragraph description of what
   the agent does.
4. Ask it to produce a draft `manifest.yaml`, `prompt.py`, `tool.py`,
   `runner.py`, and `__init__.py`.
5. **Review the generated code carefully** — LLMs are confident-wrong on
   niche scientific APIs. Verify imports, run a smoke test, and check
   that the runner correctly handles upstream errors.
6. Commit the reviewed code. From then on, TissueAgent runs the
   committed adapter deterministically; no AI is invoked at runtime to
   re-derive how to call the agent. This separation is essential for
   reproducibility in published workflows.

## Common pitfalls

- **Module-level side effects in upstream.** Many research repos do
  `openai.api_key = ...` or `tiktoken.encoding_for_model("gpt-4")` at
  import time. You must either import them inside
  `patch_openai_legacy_api`, or be sure the relevant env vars are
  populated before import.
- **Hard-coded working-directory paths.** Upstream code often writes to
  relative paths like `Outputs/foo.txt`. Wrap the call in
  `os.chdir(run_directory)` and pre-create any subdirectories the
  upstream code expects.
- **Tool argument schemas.** Avoid `Sequence[str]` in `StructuredTool`
  signatures — use `list[str]`. LangChain's schema inference is happier
  with concrete types.
- **Submodule drift.** If you patch the upstream code, commit the
  changes inside the submodule (so the SHA in `.gitmodules` advances)
  and bump `upstream.commit` in your manifest in the same PR.

## Schema reference

`manifest.yaml` is parsed by `agents.external_agent.load_manifest`,
which enforces:

| Field | Required | Type | Notes |
|---|---|---|---|
| `id` | yes | string | must match folder name |
| `name` | yes | string | human-readable |
| `version` | yes | string | semver for the adapter |
| `description` | no | string | overrides `prompt.py:Description` if set |
| `upstream.repo` | no | URL | informational |
| `upstream.commit` | no | SHA | tested commit; bumped on upgrade |
| `upstream.submodule_path` | no | string | defaults to `upstream` |
| `llm.pinned_model` | no | string | when omitted, follows TissueAgent UI selection |
| `llm.required_env_vars` | no | list[str] | listed in README for user setup |
| `data_subdir` | no | string | defaults to `id` |
| `tool.name` | no | string | informational; the real name lives in `tool.py` |
| `tool.description` | no | string | informational; the real description lives in `tool.py` |
