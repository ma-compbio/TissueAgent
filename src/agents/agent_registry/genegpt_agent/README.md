# GeneGPT

Adapter wrapping [GeneGPT](https://github.com/ncbi/GeneGPT) (NCBI, Jin et al.,
Bioinformatics 2024) — an LLM agent that answers factual genomics questions by
calling live NCBI Web APIs.

## What it does

Given a natural-language question, GeneGPT emits NCBI **E-utilities** URLs
(`esearch`/`efetch`/`esummary` over `gene`/`snp`/`omim`) and **BLAST** requests,
executes them for real, and feeds the responses back until it produces an
answer. Good for: official gene symbol / alias resolution, genomic location,
SNP↔gene and gene↔disease associations, DNA sequence alignment.

Distinct from the **Gene Agent** (which verifies a biological-process narrative
for a whole gene *set*). GeneGPT answers a single factual lookup; Gene Agent
does set-level functional interpretation.

## Credentials & requirements

- `OPENAI_API_KEY` (via TissueAgent's key registry). No extra pip install.
- **Live internet to NCBI** (E-utilities + BLAST).
- Optional `NCBI_API_KEY` raises the E-utilities rate limit (3 → 10 req/s).

## How the port works

Upstream ships as a benchmark runner (`main_turbo.py` iterating
`data/geneturing.json`) pinned to the retired `gpt-3.5-turbo-16k` via the
legacy `openai==0.27` API. The adapter:

- reuses the upstream helpers `get_prompt_header` and `call_api`,
- reimplements only the per-question tool-use loop as
  `runner.run_genegpt_question(question, mask="111111")`,
- runs it under `agents.llm_compat.patch_openai_legacy_api`, which retargets
  the loop to a current pinned model (`manifest.yaml` `llm.pinned_model`).

No changes are made inside the pinned submodule.

## Entry point

`runner.run_genegpt_question(question, mask="111111")` → structured dict with
`status`, `answer`, `api_trace`, `num_calls`, `artifact_path`. See `tool.py`.

Upstream pinned commit: see `manifest.yaml` (`upstream.commit`).
