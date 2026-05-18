# Hypothesis Agent — Handoff Document

**Branch:** `hypothesis-recovery-prototype` off `revision`
**Owner:** Mingqian (Hypothesis Agent + CellVoyager external-agent integration)
**Purpose:** Read this first if you are picking up this work. Contains the
current method, how to run it, the data we have, and what is still owed.

The work in this branch is the empirical basis for the manuscript-revision
response to **Reviewer #1 Comment #7** (Hypothesis Agent needs a benchmark)
and **Reviewer #1 Comment #6** (external-agent collaboration breadth — we
integrated CellVoyager).

---

## 1. What this branch does

### 1.1 The Hypothesis Agent (new)

Rewritten as a **three-phase, evidence-grounded recovery agent** in
`src/agents/agent_registry/hypothesis_agent/prompt.py`. The agent operates
in a persistent Python REPL across three phases:

1. **EXPLORE.** Inventory the dataset, then run ≥3 distinct EDA passes.
   At least one must satisfy the **rare-but-tight rule** (rank cell-type
   labels by spatial concentration index and report the top-3-to-5 even
   if individually <5% of cells). The agent must also log a follow-up
   observation listing the **top-3 non-self co-localizing labels** for
   each rare-but-tight population (co-localization mandate). Every
   finding is written to `data/hypotheses/exploration_log.md` as a
   structured `OBSERVATION N:` entry with concrete numbers (cell counts,
   p-values, gene lists).

2. **HYPOTHESIZE.** Form 1–3 candidate hypotheses. Each one **must** have
   a `grounded_in` field citing specific OBSERVATION numbers, a
   `test_plan`, a `predicted_outcome`, and 5-criteria quality scores
   (derivability, novelty, feasibility, specificity, falsifiability;
   0–10 each). Hypotheses are saved to `hypotheses_draft.json`.

3. **NARROW.** Execute each `test_plan` in the REPL. Decide KEEP /
   REFINE / DROP per hypothesis. Record numeric outcomes in
   `narrowing_notes`. Write final `hypotheses.json` with KEEP+REFINE
   only.

The agent ends with a `<response>` block when `hypotheses.json` is on
disk. Phase transitions are organisational; the agent does NOT emit
phase-completion markers (early prompt designs that did this caused
the agent to terminate prematurely).

### 1.2 CellVoyager as an external agent (new)

Vendored at `src/agents/agent_registry/cellvoyager_agent/upstream/` (git
submodule, pinned to commit `982a5c2`). Integration via the standard
Agent Registry interface; registered in `src/agents/agent_defns.py`.

**Dependency conflict resolution:** CellVoyager's upstream needs
`litellm` + `instructor`, both of which upgrade `openai` to ≥2.0. Our
`langchain-openai 0.3.10` requires `openai<2.0`. We resolved this by
running CellVoyager in an **isolated `cellvoyager` conda env**; the
TissueAgent runner shells out via `conda run -n cellvoyager` (see
`cellvoyager_agent/runner.py`). The two envs coexist on the same
machine without conflict.

### 1.3 Evaluation harness (new)

Two LLM-judge rubrics, both implemented with gpt-5 (high reasoning):

- **Recovery (0–8)** — `demo/eval_hypothesis_recovery.py`. Four aspects
  scored 0–2 each: spatial locus, cell-type composition, functional
  interpretation, specificity. Compares hypothesis output against a
  withheld author claim documented in
  `demo/data/<dataset>_ground_truth.md`.
- **Quality (0–50) + testability (0–3)** —
  `demo/eval_hypothesis_quality.py`. Five 0–10 sub-criteria
  (derivability, novelty, feasibility, specificity, falsifiability) +
  separate testability score. Ground-truth-free (only needs the
  hypothesis and the limited background); this is the metric the
  response document committed to.

### 1.4 Label-anonymization control (new)

`demo/build_farah_anon_h5ad.py` rebuilds the Farah dataset with the
`Populations` column renamed to opaque codes (`PA`, `PB`, ..., `PV` =
ncCM-AVC-like, `PM` = aFibro). Mapping saved at
`demo/data/farah_anon_label_map.json` for the judge only (the agent
never sees it). Tests whether the agent's recovery depends on
biologically suggestive label names or on genuine spatial discovery.

---

## 2. How to run it

### 2.1 Setup (one-time)

```bash
git clone --recurse-submodules <repo>
cd TissueAgent
git checkout hypothesis-recovery-prototype

# Main env
conda env create -f environment.yml          # creates `tissueagent` env
conda activate tissueagent
pip install -e .

# CellVoyager isolated env (needed for the external-agent comparator)
conda env create -n cellvoyager -f \
    src/agents/agent_registry/cellvoyager_agent/upstream/environment.yml
conda run -n cellvoyager pip install openai anthropic celltypist

# API keys: edit .env at repo root
echo "OPENAI_API_KEY=sk-..." >> .env
# Optional: ANTHROPIC_API_KEY=... if you want to run CellVoyager native
# or use Claude as a cross-judge.
```

### 2.2 Build datasets

```bash
# Farah (developing-heart MERFISH, 228k cells × 238 genes)
conda run -n tissueagent python demo/build_farah_h5ad.py
# Anonymized variant for label-leakage control
conda run -n tissueagent python demo/build_farah_anon_h5ad.py
```

Output: `demo/data/dataset_farah_heart_merfish.h5ad` (~70 MB) and
`demo/data/dataset_farah_anon.h5ad`. Lohoff seqFISH is already
committed at `demo/data/dataset_lohoff_et_al_seqfish.h5ad`.

### 2.3 Run a hypothesis agent recovery experiment

```bash
# Run the agent directly (bypasses the full TissueAgent graph; faster).
conda run -n tissueagent python demo/run_hypothesis_recovery.py \
    --dataset farah                     # or `farah_anon`, `lohoff`

# Artifacts land in data/hypotheses/{exploration_log.md, hypotheses.json,
# hypotheses_draft.json, hypothesis_brief.md}.
```

Typical wall-clock: ~7 min for Farah, gpt-5.1 high reasoning, ~$3 in
OpenAI tokens per run.

### 2.4 Score a run

```bash
# Recovery rubric (4-aspect, 0-8): needs <dataset>_ground_truth.md
conda run -n tissueagent python demo/eval_hypothesis_recovery.py \
    --dataset farah \
    --hypotheses data/hypotheses/hypotheses.json

# Quality rubric (5-criteria 0-50 + testability 0-3): ground-truth-free
conda run -n tissueagent python demo/eval_hypothesis_quality.py \
    --dataset farah \
    --hypotheses data/hypotheses/hypotheses.json
```

Both return structured JSON.

### 2.5 Run CellVoyager as the comparator

```bash
# Smoke test (small Lohoff dataset, ~5 min)
conda run -n tissueagent python demo/run_cellvoyager_smoke.py

# Full recovery comparison on Farah (~30-60 min depending on dataset)
conda run -n tissueagent python demo/run_cellvoyager_recovery.py \
    --dataset farah                     # or `farah_anon`
```

CellVoyager's native model is `claude-sonnet-4-6`. With only OpenAI key,
override with `--model-name gpt-5.1` (see the driver script defaults).

---

## 3. Current results

**Single paper benchmarked:** Farah et al. 2024 developing human heart
MERFISH. Withheld target: AVN/AV ring cellular community =
`ncCM-AVC-like` cardiomyocytes co-localized with atrial fibroblasts
(`aFibro`), hypothesized as a developmental precursor of the
atrioventricular node.

All runs use GPT-5.1 (high reasoning). Multi-seed = independent runs
under the same configuration (LLM stochasticity at temperature 1).

| Agent | Dataset | N seeds | recovery (0–8) | quality (0–50) | testability (0–3) |
|---|---|---|---|---|---|
| Hypothesis Agent | Farah (non-anon) | 4 | **5.0 ± 2.16** | **41.75 ± 2.21** | **3.0 ± 0** |
| Hypothesis Agent | Farah (anon) | 3 | 3.0 ± 1.73 | 39.67 ± 1.53 | 3.0 ± 0 |
| CellVoyager | Farah (non-anon) | 3 | 3.67 ± 1.15 | 35.67 ± 0.58 | 2.0 ± 0 |
| CellVoyager | Farah (anon) | 3 | 2.0 ± 1.0 | 32.0 ± 6.56 | 2.0 ± 0 |

**Three takeaways the data supports (per-seed breakdown in `RESULTS.md`):**

1. **Hypothesis quality is the headline.** The Hypothesis Agent
   consistently scores 40+ / 50 on the 5-criteria quality rubric
   (the metric the response document explicitly committed to). The
   worst HA seed (40) still exceeds CellVoyager's best (36).
2. **The HA quality advantage is design-level.** Anonymizing cell-type
   labels (e.g. `ncCM-AVC-like` → `PV`) only drops HA quality by 2.08
   points (41.75 → 39.67); CellVoyager drops 3.67 (35.67 → 32.0) and
   its variance jumps an order of magnitude. The HA-vs-CV quality gap
   *widens* after anonymization (from +6.08 to +7.67), proving the
   edge is structural, not label-driven.
3. **Recovery is variable but interpretable.** HA recovery spans
   [2, 7] across seeds. The high-variance aspects (cell-type
   composition, functional interpretation) reflect *which biological
   phenomenon* the agent commits to; the stable aspects (specificity,
   spatial locus form) reflect hypothesis-form quality. One Farah-anon
   seed recovered the exact author pair (`PV` + `PM`) via pure spatial
   discovery — no name hints.

---

## 4. Where things live

```
TissueAgent/
├── HANDOFF.md                                  ← (this would be at repo root in your fork)
├── .env                                         ← OPENAI_API_KEY here
├── demo/
│   ├── run_hypothesis_recovery.py               driver: Hypothesis Agent
│   ├── run_cellvoyager_recovery.py              driver: CellVoyager (full)
│   ├── run_cellvoyager_smoke.py                 driver: CellVoyager (smoke)
│   ├── eval_hypothesis_recovery.py              4-aspect LLM judge
│   ├── eval_hypothesis_quality.py               5-criteria LLM judge
│   ├── build_farah_h5ad.py                      builds non-anon Farah
│   ├── build_farah_anon_h5ad.py                 builds anon Farah
│   ├── data/
│   │   ├── dataset_farah_heart_merfish.h5ad     non-anon (228k×238)
│   │   ├── dataset_farah_anon.h5ad              anon variant
│   │   ├── farah_background.md                  limited background (agent sees)
│   │   ├── farah_ground_truth.md                withheld target (judge sees)
│   │   ├── farah_anon_background.md             anon background
│   │   ├── farah_anon_ground_truth.md           anon ground truth + label map note
│   │   ├── farah_anon_label_map.json            code↔original (judge only)
│   │   ├── farah_scrub_log.md                   what columns dropped + why
│   │   └── farah_raw/                           original UCSC Cell Browser files
│   └── outputs/
│       ├── HANDOFF.md                           this file (entry point)
│       ├── RESULTS.md                           data tables + per-seed snapshots
│       ├── cellvoyager_analysis.md              why CV scores 32-36 consistently
│       ├── failure_modes.md                     HA failure-mode taxonomy
│       ├── hypothesis_agent/
│       │   ├── farah/seed{1,2,3,4}/             4 seeds of HA on Farah non-anon
│       │   └── farah_anon/seed{1,2,3}/          3 seeds of HA on Farah anon
│       └── cellvoyager/
│           ├── farah/seed{1,2,3}/               3 seeds of CV on Farah non-anon
│           ├── farah_anon/seed{1,2,3}/          3 seeds of CV on Farah anon
│           └── lohoff_smoke/                    smoke-test on Lohoff
└── src/
    └── agents/
        ├── agent_defns.py                        cellvoyager_agent registered here
        └── agent_registry/
            ├── hypothesis_agent/
            │   ├── prompt.py                     ★ the three-phase prompt
            │   ├── model.py                      CodeAct loop
            │   ├── tools.py                      tool defs
            │   └── params.py                     model selector
            └── cellvoyager_agent/
                ├── manifest.yaml                 declarative metadata
                ├── prompt.py                     adapter prompt
                ├── runner.py                     subprocess into isolated env
                ├── tool.py                       StructuredTool wrapper
                ├── __init__.py                   ExternalAgentDefinition
                └── upstream/                     git submodule @ 982a5c2
```

Each per-seed artifact directory contains:
- `exploration_log.md` — Phase 1 observations
- `hypotheses_draft.json` — Phase 2 candidates
- `hypotheses.json` — Phase 3 final retained hypotheses
- `hypothesis_brief.md` — human-readable summary
- `transcript.log` — full agent transcript (every LLM turn + REPL output)

For CellVoyager seeds, the `outputs/<analysis_name>/*.ipynb` are full
Jupyter notebooks; `cellvoyager_recovery_summary*.json` is the parsed
hypothesis cells.

---

## 5. What is still owed for the manuscript

These items are committed in the response document but not yet shipped:

**Blocking (per response-doc commitments):**

1. **N ≥ 2 more recovery papers.** The response uses plural "studies".
   Currently only Farah is benchmarked. Each new paper needs:
   `<paper>_background.md` (intentionally vague, no target claim) +
   `<paper>_ground_truth.md` (withheld target + 4-aspect rubric).
   Lohoff seqFISH is already on disk but lacks a curated target.
2. **Expert-scored evaluation.** The response says "expert-scored
   evaluation of generated hypotheses using the [5] criteria". We have
   only LLM-judge scores. Need ≥ 10 hypotheses scored by a domain
   expert and inter-rater agreement reported.
3. **Cross-LLM judge.** Reviewer #3 Comment #4.3 flagged that GPT
   judging GPT is conflict-of-interest. Need a Claude (or non-GPT)
   judge run on the same hypotheses; report agreement.

**Strongly recommended:**

4. **CellVoyager native model.** All CV numbers above used GPT-5.1
   because we have no Anthropic key. CV's published config is
   `claude-sonnet-4-6`. Needs `ANTHROPIC_API_KEY` then a re-run of
   the multi-seed protocol.
5. **Backbone-model ablation** (also addresses Reviewer #2 Comment #4
   and Reviewer #3 Comment #1.6). Re-run HA on GPT-4o + Claude
   Sonnet/Opus at minimum; check whether the design-level edge holds.

**Smaller polish:**

6. **Honesty-trap fix.** In one anonymized seed, Phase 3 dropped all
   hypotheses because the proposed `predicted_outcome` cited
   proliferation (p=0.047 marginal) while the test actually revealed a
   strong signal in developmental TF program (p=4.13×10⁻⁷). The
   narrowing rule should REFINE-by-switching-program rather than DROP
   when an *adjacent* program shows clear signal. Small prompt patch.
7. **Recovery rubric expansion.** Current rubric only credits hypotheses
   that match the author's specific claim. Many HA seeds find real but
   different biological communities (e.g. adFibro+LEC lymphatic
   interface). A "biological validity" dimension would credit these
   honest non-recoveries.

**Scope decisions for the team:**

8. **BARD vs BRAD.** The response document names "BARD" as a committed
   external-agent integration alongside CellVoyager and Paper2Agent.
   The only matching LLM agent in the field is `Jpickard1/BRAD`
   (Bioinformatics 2025) — almost certainly a typo. Confirm spelling
   before the response goes back to reviewers.
9. **Paper2Agent integration.** Paper2Agent (`jmiao24/Paper2Agent`,
   Stanford) is a factory that converts research papers into MCP
   servers, not a single agent. Integration pattern differs from
   GeneAgent/CellVoyager (we would consume the MCP, not subprocess the
   tool). Scope ownership TBD.

---

## 6. Known design choices and their tradeoffs

### 6.1 Why explore-narrow-hypothesize, not generate-then-execute?

CellVoyager's design generates a hypothesis once (in `first_draft.txt`)
and then refines its analysis plan. The hypothesis itself is immutable
across the iteration loop. This produces consistent quality but locks
the framing: all 18 CellVoyager hypotheses we observed on Farah fit
the template "Within X cell type, Y correlates with metadata Z" —
cross-population community findings are structurally out of reach.

Our three-phase design forces ≥3 exploration passes *before* hypothesis
formation and explicitly rewards multi-cell-type co-localization. The
tradeoff is higher recovery variance ([2, 7] vs CV's [3, 5]) but a
much higher ceiling (best run 7/8 vs CV's 5/8) and consistently
higher quality.

### 6.2 Why no `<phase_done>` marker?

Earlier prompt designs asked the agent to emit
`<phase_done>EXPLORE</phase_done>` between phases. The graph router
treated such a turn (no `<execute>` and no `<response>`) as "direct
response, exit", terminating the run after Phase 1. Removed; phases
are now organizational only. Every non-final turn must contain an
`<execute>` block.

### 6.3 Why `Communities` and `Zone_Cluster` are scrubbed from Farah .obs

The published Farah dataset includes a `Communities` column whose
values include the literal string `AVN/AV Ring` — the exact recovery
target. `Zone_Cluster` is its integer alias. Both are dropped at h5ad
build time (see `farah_scrub_log.md`). The agent never sees them; the
judge does not need them.

### 6.4 Why label anonymization is non-optional

`ncCM-AVC-like` literally contains the substring "AVC", which is the
target anatomical region. Without anonymization, recovery is partially
explained by label-text pattern matching rather than genuine spatial
discovery. We report both anon and non-anon numbers. **Anon is the
defensible baseline for any claim of biological discovery.**

### 6.5 Why testability is constant 3.0 for HA, 2.0 for CellVoyager

Our Phase 3 narrowing executes each hypothesis's `test_plan` in the
REPL and reports numeric results (Wilcoxon p-values, group means).
The judge picks this up and scores testability = 3. CellVoyager
generates analysis plans but does not execute them in a way our
notebook parser recognizes — testability = 2. This is a structural
property of the two designs, not a tuning parameter.

---

## 7. Quick-start checklist for the next person

- [ ] Clone, switch to `hypothesis-recovery-prototype` branch, init submodules
- [ ] Build `tissueagent` and `cellvoyager` conda envs
- [ ] Set `OPENAI_API_KEY` (and `ANTHROPIC_API_KEY` if available) in `.env`
- [ ] Build Farah datasets (`build_farah_h5ad.py`, `build_farah_anon_h5ad.py`)
- [ ] Run a smoke test: `run_hypothesis_recovery.py --dataset lohoff`
      (uses small dataset, ~5 min, verifies the pipeline)
- [ ] Run one Farah seed: `run_hypothesis_recovery.py --dataset farah`
      (~7 min, should yield artifacts in `data/hypotheses/`)
- [ ] Score: `eval_hypothesis_recovery.py` + `eval_hypothesis_quality.py`
      against the artifacts
- [ ] Pick a manuscript-blocking item from section 5 and proceed

If anything breaks, check `transcript.log` in the per-seed dir; the
agent's full reasoning + REPL output is captured there.
