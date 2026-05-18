# CellVoyager Framing Analysis — Why It Scores the Way It Does

**Purpose:** systematic look at all 18 unique hypotheses CellVoyager
generated across 6 runs on Farah (3 non-anon + 3 anon, all GPT-5.1).
Why does CellVoyager consistently score 32–36 / 50 on quality and miss
the AVC/AVN claim on recovery, but with quality SD as small as 0.58?

---

## The framing template

**Across all 18 CV hypotheses on Farah, the framing fits a single
template:**

> *"Within [some cell population], [some spatial/neighborhood metric]
> is systematically associated with [transcriptional metric, usually
> `Complexity` / `Purity` / Sample]."*

This is consistent regardless of seed, regardless of model anonymization,
and regardless of which specific cell populations or metrics get
substituted into the slots.

Concrete fillings observed:

| Slot | Examples (across 18 hypotheses) |
|---|---|
| **cell population** | ventricular cardiomyocyte subtypes; fibroblasts; "each major cardiac cell population"; "each annotated population"; "each anonymized cardiac cell population"; "transcription-factor–rich cardiac populations" |
| **spatial / neighborhood metric** | neighborhood composition; spatial gradients of TF expression; spatial neighborhood diversity (heterotypic vs homotypic); cell density / crowding; co-localization with specific neighbors; same-type clustering vs dispersion; spatial autocorrelation |
| **transcriptional metric (target)** | transcriptional complexity; sample-wise Purity; intra-population transcriptional heterogeneity; per-cell transcriptional complexity + Purity; maturation state via Purity/Complexity; "microenvironment-dependent maturation or stress states" |

## What's notably absent

In **none** of the 18 hypotheses does CellVoyager propose:

1. A specific **multi-cell-type community** at a named anatomical locus.
   E.g., "ncCM-AVC-like cardiomyocytes + atrial fibroblasts form a
   distinct community in the AVC region" — the form of the Farah
   author claim — never appears in CV output.
2. A **developmental / progenitor** interpretation. The framing stays on
   "maturation / stress / quality state" but doesn't reach "this is a
   developmental progenitor for AVN".
3. Anatomical **region-specific** claims beyond generic
   ventricle-vs-atrium contrast. No "AVC", no "AV ring", no
   "conduction system".
4. **Cross-population** community discovery. The "Within X population"
   clause is invariant — every hypothesis restricts the analysis to
   one population at a time and asks about its internal heterogeneity,
   rather than asking which populations form communities together.

## Where the framing template comes from

We read the upstream `cellvoyager/prompts/first_draft.txt` and
`hypothesis.py:HypothesisGenerator`. The relevant design choices:

1. **`first_draft.txt` is shown the AnnData `.obs` columns.** All of
   `Complexity`, `Purity`, `Sample_ID`, `UMI Count`, `leiden`,
   `Populations` are present. These are the most "quantifiable" columns
   in the .obs.
2. **The prompt instructs the LLM to propose a hypothesis "distinct
   from the paper and prior analyses".** Without a paper summary
   (intentional, our setup), "distinct from prior analyses" defaults
   to the most-quantifiable structure in the visible metadata.
3. **The hypothesis is locked at idea-generation time.** `hypothesis.py`
   line 191: `analysis["hypothesis"] = hypothesis`. Critique can refine
   the *plan* but not the *hypothesis*. So the LLM's first guess at
   the most-quantifiable structure becomes the hypothesis for all 6
   iteration steps.
4. **No exploration-before-commit phase exists.** Unlike our HA's
   Phase 1, which requires logged OBSERVATIONs *before* hypothesis
   formation, CellVoyager's `first_draft.txt` calls the LLM with just
   `(adata_summary, paper_summary, attempted_analyses)` and asks for
   the full `AnalysisPlan` (hypothesis + plan + first_step_code) in
   one shot.

The result: when fed an AnnData with `Complexity` and `Purity` in
`.obs`, gpt-5.1 with the CellVoyager prompts reliably picks
"within-population × neighborhood × Complexity/Purity" as the
"most-quantifiable" hypothesis. This is what we see in every seed.

## Consequence for the score profile

The framing template explains all of CellVoyager's score patterns:

| Score / pattern | Reason |
|---|---|
| Quality 35.67 ± 0.58 (non-anon) — very tight | Template fully specifies the form; seed only changes wording |
| Recovery 3.67 ± 1.15 (non-anon) — partial misses | Template doesn't include "named community at anatomical region"; recovery target is exactly that form |
| Testability 2.0 ± 0 (constant) | Each plan is concrete enough to be executable; no execution step parsed |
| Quality drops to 32.0 ± 6.56 under anonymization | Template depends on named cell-population labels for grounding specificity; opaque codes break the specificity scoring |
| Quality SD jumps from 0.58 → 6.56 under anonymization | The template needs to flex when label scaffolding is removed, exposing the LLM to more degrees of freedom |
| Best CV recovery 5 (anon seed#1, "interfaces between V and A territories") | Outlier seed where the LLM happened to substitute "interface" for the typical "within-population" — closer to the cross-population community framing of the Farah claim |

## What CellVoyager IS doing well

It's important to note: CellVoyager's hypotheses are NOT bad science. On
the quality rubric:

- **Derivability** 6–7 / 10 typical — claims are plausible extensions of
  the visible data structure.
- **Novelty** 6–8 / 10 — "Complexity-neighborhood coupling" isn't a
  trivial restatement of background knowledge.
- **Feasibility** 6–8 / 10 — analyses use available `.obs` columns,
  k-NN, simple statistical tests.
- **Specificity** 7–8 / 10 (non-anon) — concrete inputs and predicted
  directionality.
- **Falsifiability** 8–9 / 10 — clear null predictions, regression
  controls, paired tests.

CellVoyager's framing is just *narrow*. The agent is consistently
proposing a particular kind of hypothesis — and consistently proposing
it well. It's structurally unsuited to recover a multi-cell-type
spatial-community claim about a small, anatomically specific region.

## Implications for the manuscript

This isn't a "we beat CellVoyager" story; it's a "different agents
make different inductive priors" story.

- **CellVoyager** is well-suited to discovering quantitative,
  metadata-driven, within-population effects — which is exactly the
  flavor of analysis its design (single-cell scRNA-seq, hypothesis-lock,
  programmatic kernel execution) was built for.
- **TissueAgent's Hypothesis Agent** is well-suited to discovering
  multi-cell-type spatial communities and cross-population structure —
  because the explore-narrow-hypothesize loop forces broad EDA before
  commitment and rewards co-localization observations explicitly (in
  the rare-but-tight + co-localization mandate, though we showed
  multi-seed that the mandate's marginal effect is within seed noise).
- The right framing for Comment #6: TissueAgent's external-agent
  contract successfully integrates an agent with a fundamentally
  different inductive prior than TissueAgent's own agents. This
  *demonstrates* interoperability — the Manager incorporates
  CellVoyager's narrow-framing hypotheses into the evolving plan
  alongside HA's broader-framing hypotheses without modification.

## Caveat that limits the conclusion

CellVoyager's framing on Farah was generated under GPT-5.1, not under
its native `claude-sonnet-4-6`. The framing-template story above is
robust *to gpt-5.1*. Whether `claude-sonnet-4-6` would produce a
materially different framing pattern on the same dataset is unknown
without the Anthropic key. The hypothesis-lock mechanism (in
`hypothesis.py:191`) is model-agnostic; the framing dependence is on
which prior the LLM's first-shot generates in response to
`first_draft.txt`.

A clean follow-up: rerun the same 6-run protocol with
`claude-sonnet-4-6` and compare framing patterns. The framing template
is the most-likely source of any model-dependent score gap.
