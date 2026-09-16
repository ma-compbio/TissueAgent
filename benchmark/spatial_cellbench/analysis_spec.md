# Spatial CellBench analysis specification

## Primary observations

For candidate \(c_i\) and the complete ground-truth set \(G\), GPT-4o returns one independent
binary decision indicating whether \(c_i\) matches any member of \(G\). For a paper with N
candidates, the score is:

\[
\frac{1}{N}\sum_i 1\{c_i\text{ matches any analysis in }G\}.
\]

Duplicate credit is allowed and no one-to-one assignment is applied. The judge sees only each
candidate's title and detailed summary plus shuffled ground-truth titles and descriptions. It
does not see the arm, paper title, generation trace, or recruitment state.

Report both:

- mean-paper hit: average candidate hit fraction after averaging three replicates within paper;
- pooled-candidate hit: total matched candidates divided by total candidates.

The upstream repository calls these quantities `micro_avg` and `macro_avg`, respectively, but
those names are reversed relative to common macro/micro usage; this benchmark uses descriptive
names.

## Contrasts

The frozen paired paper-level contrasts are:

- `tissueagent - direct`;
- `tissueagent_spatial_cv - tissueagent`.

The last is an explicit integration-treatment contrast. Every TA+CV unit must recruit and invoke
Spatial-CV for the draft and expose its validated artifact to final Hypothesis synthesis. A
noncompliant run fails generation and is not silently treated as TA+CV.

Each arm must have replicate IDs 1, 2, and 3 for a paper before that paper enters a contrast.
Replicates are averaged within paper, the paper is the statistical unit, and uncertainty is a
10,000-sample paired paper bootstrap with seed 20260720. Missing or failed units are not imputed.
The eleven method-heavy papers form a descriptive benchmark; intervals are uncertainty summaries, not
a basis for broad method-superiority claims.

## Protocol boundaries

- Every generator receives the same frozen public context and the true paper-specific N.
- Ground-truth content and source-paper identity remain controller-only during generation.
- Direct makes one call; every TA+CV unit makes exactly 3N calls inside its recruited
  Spatial-CV draft step.
- All candidate-generating workers use o3-mini with medium reasoning. Native TA orchestration
  uses the production default GPT-5.1; all judges use GPT-4o.
- Direct, the judge, and each benchmark Hypothesis invocation do not
  self-correct malformed semantic output, switch prompts, or fall back to another model.
  Provider-level transient-error retry does not change model or prompt. The native Hypothesis
  tool loop may correct rejected Python/tool syntax before any artifact has validated; it stops
  immediately after the first valid write and does not revise that artifact.
- The native graph retains its production Planner/Recruiter format handling, Manager retry-step,
  and Evaluator replan behavior; these are part of the tested method and remain visible in its
  trace. The benchmark controller never retries a failed unit automatically. An explicit
  `--retry-failed` archives the failed checkpoint and creates a separately recorded attempt.
- Both native arms use the same paper-independent draft -> critique -> final workflow. TA+CV adds
  one method-defining instruction assigning the draft to its added Spatial-CV agent. Recruitment,
  invocation, valid trace production, and exposure to final Hypothesis synthesis are required and
  audited.
- Native Manager writes and role/plan compliance are recorded rather than prohibited. The final
  artifact must match an audited native-agent tool call and pass the frozen schema.
- Malformed or missing generation artifacts fail the unit rather than shrinking its denominator.
