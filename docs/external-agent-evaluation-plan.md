# Evaluating the External Agents

_How to evaluate TissueAgent's four external agents and present the results. Drafted 2026-08-21._

## Current state

At HEAD there is **no evaluation of any external agent**. `INTEGRATING.md` §10 asks only that a
contributor "confirm that the agent loads, runs end-to-end against a small input" — a manual
smoke test, not a protocol. No test, benchmark, or notebook in the working tree invokes any of
the four adapters.

What does exist is ad-hoc smoke runs left in `projects/`, unscored and unaggregated, but with
artifacts already rich enough to seed case studies (see §3):

| Agent | Runs | Example artifact |
| --- | ---: | --- |
| gene_agent | 7 | `projects/2026-07-06_22-17-22/outputs/gene_agent/aFibro_AVN-AVring/` |
| genegpt | 8 | `projects/2026-07-24_15-28-00/outputs/genegpt/LMP10_lookup_1/result.json` |
| mllmcelltype | 4 | `projects/2026-07-06_21-15-05/outputs/mllmcelltype/run_*/` |
| cellvoyager | 0 | — |

### A real CellVoyager benchmark existed and was deleted

This is the most useful thing to know before building anything. Commit `1cb8356`
("Add full-graph hypothesis-recovery three-arm benchmark", 2026-07-12) added a complete
evaluation that **invoked the real adapter** — `demo/run_hypothesis_recovery.py:168` imports
`run_cellvoyager_analysis` from `agents.agent_registry.cellvoyager_agent.runner`. Commit
`00a9ab3` ("Replace legacy recovery benchmark with CellBench comparison", 2026-07-16) removed it.

Its design is precisely the protocol §2 would otherwise have to reinvent, and it is the origin of
the "Reviewer #1 Comment #7" framing that now survives at HEAD only as a stale sentence in
`cellvoyager_agent/manifest.yaml`. Three arms on identical full-size inputs, withheld background,
gold claims never shown to the agent:

- **TissueAgent alone** — full graph, CV excluded from the recruitable pool (a true ablation)
- **CellVoyager alone** — via the `cellvoyager_agent` adapter
- **TissueAgent + CellVoyager** — full graph, CV in the pool, recruiter decides

Recoverable with `git show 1cb8356:<path>`: the runner (532 lines), `run_recovery_batch.py`,
`score_hypothesis_recovery.py` (329 lines), `README.md`/`METHODS.md`, five fixtures each with
`background.md` + `gold_claims.json` + `dataset_manifest.json`, and real CellVoyager run outputs
under `results/<fixture>/cellvoyager/`.

Two cautions if you revive it. Its own results are labeled *"heuristic scorer v1 — Do not quote
these numbers in Response without expert audit"*, so the scorer needs replacing with an
arm-blind LLM judge before anything is quoted. And CV-alone execution rate was **0.00 across all
fixtures** — the agent produced suggestions but nothing runnable. That is either a genuine finding
about CellVoyager or an adapter defect, and it must be resolved before publishing either way.

**Reviving this is the recommended first move for CellVoyager** — recover the fixtures and
harness from `1cb8356`, swap in a proper judge, rather than starting from `upstream/CellBench`.

### Spatial CellBench does not evaluate the adapter

Spatial CellBench's headline result — TA+CV at 55.08% vs TA at 47.24%
(`docs/spatial_cellbench_results.md`) — is **not** an evaluation of the `cellvoyager_agent`
external agent. That arm is a CellVoyager-*style* reimplementation:
`benchmark/spatial_cellbench/prompts.py:37` builds "one minimally spatialized upstream CellVoyager
draft prompt," borrowing prompt text from the vendored submodule (`corpus_manifest.json:43`),
while nothing under `benchmark/` imports `agent_registry`. It replaced the harness that *did* call
the adapter. Worth stating explicitly in any paper text, since "CellVoyager" currently means two
different things in this repo.

## 1. The opportunity: every upstream ships its own ground truth

This is the thing that makes the whole evaluation cheap. All four upstreams are vendored as
pinned submodules, and three carry benchmark data plus an official scorer:

| Agent | Ground truth (vendored) | Size | Official metric |
| --- | --- | ---: | --- |
| **genegpt** | `upstream/data/geneturing.json`, `genehop.json` | 450 + 150 Q | `upstream/evaluate.py` — exact match w/ per-task normalizers |
| **gene_agent** | `upstream/Datasets/{Gene ontology,MsigDB,NeST}` | 1000 GO + 56 MsigDB + 50 NeST sets | `upstream/evaluate.ipynb` |
| **cellvoyager** | 5 fixtures w/ `gold_claims.json` in `git show 1cb8356`; also `upstream/CellBench/data/cellbench_50.csv` | 5 papers / 99 papers | deleted `score_hypothesis_recovery.py`; `upstream/CellBench/run_llm_judge.py` |
| **mllmcelltype** | none shipped (`notebooks/demo_data` is cached output only) | — | needs an external annotated dataset |

Using the upstream's own metric is the strongest possible framing: it lets you report **"our
adapter reproduces the published number"**, which is an integration-fidelity claim reviewers
accept without argument. It also catches adapter regressions — the pinned-model retargeting is
exactly the kind of change that silently degrades accuracy.

The one caveat is that GeneTuring/GeneHop accuracy depends on live NCBI responses, which drift
from the 2024 paper. Report your number against upstream's published one and treat a gap as
provenance to investigate, not automatic adapter failure.

## 2. Proposed protocol

Follow the conventions already established in `benchmark/` — they're rigorous and reviewers will
see one consistent methodology rather than a bolted-on appendix.

**Call the runners directly, not the LLM wrapper.** Each adapter exposes a clean Python entry
point, so the harness can be deterministic and skip the ReAct loop entirely:

- `genegpt_agent/runner.py:136` → `run_genegpt_question(question, mask="111111")`
- `gene_agent/runner.py:194` → `run_geneagent_cascade(...)`
- `mllmcelltype_agent/runner.py:145` → `run_mllmcelltype_annotation(...)`
- `cellvoyager_agent/runner.py:176` → `run_cellvoyager_analysis(...)`

Conventions to inherit:

- **Unit of record** = one `(agent, task_id, seed)` triple emitting one `metrics.json`; aggregate
  as a pure function of the run corpus so it re-derives without re-running
  (`docs/benchmark-metrics-spec.md` §1).
- **N = 3 replicates**, giving pass@1 and pass@3 — these agents are as stochastic as any other.
- **Arm-blind judge that is not a contestant.** `grade.py` is explicit that self-grading is a
  conflict of interest. GeneGPT/GeneAgent need no judge (exact match); CellVoyager does.
- **Immutable, resumable checkpoints** with `--skip-judge` / `--retry-failed`, per
  `spatial_cellbench/run.py`.
- **Record the submodule SHA and pinned model in every run.** These are the two variables the
  whole exercise controls for.

Suggested layout, mirroring the existing benchmarks:

```
benchmark/external_agents/
  geneturing/       # genegpt, 600 Q, upstream exact-match scorer
  geneagent_sets/   # gene_agent, GO/MsigDB/NeST
  cellbench_cv/     # cellvoyager, LLM judge
  results/
```

Two cost notes. GeneTuring's 600 questions × 3 seeds × multiple live NCBI calls each is the
expensive arm — subsample per task (e.g. 20 of 50 × 9 tasks = 180 Q) and say so, rather than
silently truncating. Setting `NCBI_API_KEY` raises the rate limit 3→10 req/s, which is close to
required at this volume; note that the key is declared in `genegpt_agent/manifest.yaml` as
`optional_env_vars` but **nothing in `src/` reads it**, so that path needs wiring first.

**A cheap first step, independent of all the above:** a manifest-consistency test asserting each
agent imports, its submodule sits at the pinned commit, and its tool name matches its manifest.
That's minutes of work, runs in CI without API keys, and catches the failure mode most likely to
silently break a published result.

## 3. Case studies: what to show

Benchmarks answer "is it correct." Case studies answer "why is it worth integrating" — and for
external agents that second question is the interesting one, because the honest headline is
*capability that TissueAgent does not otherwise have*, not accuracy.

Follow `demo/`'s existing pattern: one self-contained notebook per task, run top-to-bottom,
outputs to `demo/outputs/{TASK}/` with a `transcript.log`.

The strongest case study for each agent, given what the artifacts already show:

**GeneGPT — verifiable tool use against live databases.** The `result.json` already captures a
full `api_trace`: resolving alias `LMP10` → `PSMB10` via a real `esearch` → `efetch` chain
against NCBI. Show the trace. The point is that the answer is *checkable* — every claim maps to a
URL a reader can re-run — which is a categorical difference from a model answering gene questions
from memory. That is the single most reviewer-legible artifact any of the four produces.

**GeneAgent — claim verification, including when it refuses.** The existing run on the
`aFibro_AVN-AVring` set produced structured `processes` with `supporting_genes`, plus a `notes`
field recording that verification "did not support narrow, AV node/annulus-specific" claims.
Show that. An agent that declines to support an over-specific claim is demonstrating the
verification cascade working, and it is far more persuasive than a clean success.

**mLLMCelltype — consensus as a confidence signal.** Run in `consensus` mode on a dataset with
known labels and show the per-cluster consensus proportion and Shannon entropy against
correctness. The claim to test: entropy flags the clusters that are actually wrong. If it does,
that is a genuinely useful calibration signal; if it doesn't, that's worth knowing before relying
on it.

**CellVoyager — end-to-end autonomous analysis.** Zero artifacts at HEAD, but the deleted
benchmark holds real run outputs under `results/<fixture>/cellvoyager/hypotheses.json` and the
three-arm design gives the case study its shape directly: same paper, same withheld background,
what TA finds alone vs. what CV contributes vs. what the two find together. The recorded
0.00 CV-alone execution rate is itself the honest finding to investigate and, if real, to report.

For each, report cost alongside quality — mean model calls, tokens, wall time — exactly as
`spatial_cellbench_results.md` does. These agents make many live API calls, and an integration
that triples cost for a small accuracy gain should be presented as such.

## 4. Presenting results

Reuse `docs/spatial_cellbench_results.md` as the template — main comparison table, per-task
breakdown, cost-and-integrity section, reproducibility footer with commit hashes. Two habits from
that document are worth carrying over specifically:

- **State when an interval includes zero.** It calls its own headline "evidence of an integration
  signal rather than a statistically established superiority claim." Per-task external-agent
  numbers will be small-n too.
- **Retain irregularities rather than rerunning them selectively.** It documents two bookkeeping
  irregularities it chose not to rerun. Same discipline here.

The comparison that actually matters is **external agent vs. TissueAgent's native path on the
same task** — GeneGPT vs. the coding agent answering the same lookup, mLLMCelltype vs.
`cell_annotater_agent` on the same clusters. That tells you whether each integration earns its
maintenance cost, which is the question a reviewer will ask and the one nothing currently answers.

## 5. Known defects to fix first

1. **`cellvoyager_agent/README.md` is a verbatim copy of the template** — byte-identical to
   `_template_external_agent/README.md`, still titled "`_template_external_agent` (do not edit in
   place)" and instructing the reader to copy the folder. It documents nothing about CellVoyager.
2. **`required_env_vars` is never enforced.** Parsed into the dataclass at
   `src/agents/external_agent.py:54` and never read again — a missing key fails deep inside a
   runner mid-run instead of at wiring time. A benchmark harness needs this as a preflight or
   long runs die partway.
3. **`optional_env_vars` is dead** — declared in `genegpt_agent/manifest.yaml`, read nowhere.
4. **`docs/benchmark-metrics-spec.md:86` points at a deleted file** — "Precedent to reuse:
   `demo/score_hypothesis_recovery.py`" no longer exists at HEAD (removed in `00a9ab3`). Either
   restore it from `1cb8356` or drop the reference.
5. **`genegpt_agent` is missing from the README external-agents table** (`README.md:366-368`
   lists only GeneAgent, CellVoyager, mLLMCelltype), and
   **`cellvoyager_agent/manifest.yaml:9-13` cites a benchmark that no longer exists** at HEAD.
