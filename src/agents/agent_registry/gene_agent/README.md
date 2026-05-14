# Gene Agent (external adapter)

This folder integrates **NCBI's GeneAgent** into TissueAgent.

- **Upstream:** https://github.com/ncbi-nlp/GeneAgent
- **Pinned commit:** see `manifest.yaml` → `upstream.commit`
- **What it does:** Given a gene list, the agent proposes a biological-process
  name and verifies it against curated biological databases (GO, KEGG,
  NCBI Gene summaries, UniProt, PubMed). Returns a process-level narrative
  with evidence.
- **What it does NOT do:** Enrichment-style outputs (GO/GSEA tables,
  dotplots, volcano plots, ranked TSVs).

## File layout

```
gene_agent/
├── manifest.yaml        Declarative metadata (id, version, upstream pin, env vars)
├── README.md            This file
├── __init__.py          Exports `agent_definition: ExternalAgentDefinition`
├── prompt.py            System prompt + description shown to the recruiter
├── tool.py              The single StructuredTool the manager invokes
├── runner.py            The adapter that calls the upstream code
└── upstream/            Git submodule, ncbi-nlp/GeneAgent at the pinned commit
```

## LLM compatibility

The upstream GeneAgent was written against the legacy `openai==0.28` API
(`openai.ChatCompletion.create`), uses Azure-style `engine=` arguments,
and hard-codes a model choice. TissueAgent ships modern `openai>=1.73`,
where `ChatCompletion` was removed.

The adapter handles all of this through `agents.llm_compat.patch_openai_legacy_api`,
which monkey-patches the `openai` module for the duration of one
invocation:

- Provides a `ChatCompletion.create(...)` shim that proxies to the modern
  `OpenAI().chat.completions.create(...)`.
- Ignores `engine=` and any caller-supplied `model=`.
- Pins the model to `gpt-5.1` (configured in `manifest.yaml`), independent
  of TissueAgent's UI model selection. This keeps GeneAgent's behavior
  reproducible across sessions.
- Uses the OpenAI API key from TissueAgent's runtime key registry (env
  var or UI-pasted key).

## Required credentials

- `OPENAI_API_KEY` — set in the environment or pasted into the web UI's
  *API keys* panel.

GeneAgent does **not** use the Anthropic or OpenRouter keys, even if you
have selected a Claude model elsewhere in TissueAgent.

## Output artifacts

The adapter creates `data/gene_agent/<request_id>/` and runs the upstream
cascade inside it as the working directory. The upstream code expects to
write to relative paths like `Outputs/GeneAgent/Cascade/...` and
`Verification Reports/Cascade/...`; the adapter pre-creates those
directories.

## Updating the upstream pin

```bash
cd src/agents/agent_registry/gene_agent/upstream
git fetch
git checkout <new-sha>
cd -
# bump `upstream.commit` in manifest.yaml
# re-run a smoke test
git add manifest.yaml src/agents/agent_registry/gene_agent/upstream
```
