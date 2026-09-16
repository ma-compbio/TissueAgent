# BioMysteryBench-Expression (`BMB-Expr`)

A **20-task subset** of [BioMysteryBench](../upstream) (Anthropic, **v11**, 90
problems) curated for **TissueAgent**. Every task here **ships a gene-expression
matrix** and is solvable through expression analysis — the core competency of
TissueAgent's expression engine (marker-gene annotation, differential expression,
clustering, signature matching).

Tasks that require read-level alignment, variant/WGS calling, methylation/ATAC
peak-typing, mass-spec, protein structure, or microbiome profiling are **excluded**
— those belong to a general bioinformatics agent, not TissueAgent. As of
2026-07-28 that exclusion is enforced against **what each task's zip actually
contains**, not merely how the question is worded; see §Non-matrix exclusions.

> **Scope note:** these tasks exercise TissueAgent's *expression-analysis* engine.
> They are **not** spatial and are mostly **bulk** matrices, so they do **not**
> test spatial-domain detection, cell-cell communication, or spot deconvolution.

## Buckets (named by the skill they exercise)

| Bucket | Tasks | Human-solvable (yes/no) | TissueAgent skill |
|---|---|---|---|
| `annotation` | 9 | 8 / 1 | cell-type / tissue marker annotation |
| `differential-expression` | 7 | 5 / 2 | DE between conditions / perturbation ID |
| `clustering` | 4 | 3 / 1 | unsupervised grouping / sample splitting |
| **total** | **20** | **16 / 4** | |

Task count fell 34 → 20 in two independent steps: upstream v11 deleted 4 curated
tasks (§Rebuilt for upstream v11), and an audit removed 10 more that were never
expression-matrix tasks (§Non-matrix exclusions).

## Non-matrix exclusions (2026-07-28)

The v8 curation admitted 10 tasks that violate the subset's own scope. An audit of
what each zip actually ships removed them. **Two are not expression assays at
all**; **eight ship raw FASTQ** and require alignment + quantification before any
expression analysis begins — which measures whether the coding agent can drive an
aligner, not the expression engine.

| id | bucket | what the zip actually contains |
|---|---|---|
| `hb026` | annotation | `hb026_subsampled_data.tsv` — snATAC-seq fragments |
| `reczkg8fvfp1fo3nn` | annotation | `h3k27ac_peaks.bed.gz` — ChIP-seq peaks; asks for super-enhancer profiling |
| `hb045` | annotation | 6-part FASTQ tarball (~3.7 GB) |
| `rec1vycgih4bavtur` | differential-expression | 2 × FASTQ |
| `reccipvrmk1k0gqkr` | differential-expression | 2 × FASTQ |
| `recffr4vmqdynph2n` | differential-expression | 2 × FASTQ |
| `recnquldskiadnpq8` | differential-expression | 24 × FASTQ |
| `recqjfzttushuxz4j` | differential-expression | 2 × FASTQ |
| `recnayu0v8zttjlgf` | clustering | 30 × FASTQ |
| `reccwgc4buredxvyz` | clustering | 36 × FASTQ + 1 metadata csv, **27.5 GB** — the largest task in the benchmark |

Empirically these were also the worst value in the benchmark. In the pre-v11
corpus (`grades_2026-07-26_v3.csv`, single replicate) TissueAgent scored **1/8 on
the FASTQ group vs 8/20 on matrix tasks**, and the two most expensive failures in
the entire benchmark were FASTQ tasks: `rec1vycgih4bavtur` (1.65M tokens, 78 min)
and `recffr4vmqdynph2n` (1.05M tokens, 84 min). The three tasks with the most
files finished in 9–11 minutes — too fast to have aligned anything. Note n is
small enough that 1/8 vs 8/20 is not statistically separable on its own; the
format audit, not the score gap, is the reason for removal.

`build_expr.py --keep-nonmatrix` restores them for reproducing a pre-2026-07-28
run. **Do not pool 20-task numbers with 30- or 34-task numbers.**

> `reccwgc4buredxvyz` was missed on the first audit pass: its zip had arrived
> truncated, so `unzip -l` reported no entries and it was classified as having no
> files rather than as unreadable. Restoring it from the LFS object exposed 36
> FASTQ files. Any future audit should treat an unreadable archive as unknown,
> never as empty.

## Rebuilt for upstream v11 (2026-07-28)

Upstream v11 removed 9 problems after a June 2026 expert audit and edited 24
more. **Results from the 34-task v8 subset are not comparable to this one** and
must not be pooled. Three separate reasons, each sufficient on its own:

1. **4 of the 34 tasks are gone** — upstream deleted them for defective answer
   keys, so old scores on them were graded against keys upstream now disavows:

   | id | bucket | upstream's reason |
   |---|---|---|
   | `hb022` | differential-expression | key inverted relative to hallmark erastin markers |
   | `hb053` | differential-expression | underdetermined — expert benchmarkers disagreed with the key and each other |
   | `hb027` | clustering | underivable — the 173/217 case/control split is not recoverable from the data |
   | `hb006` | clustering | key listed `Sample_1`–`Sample_74` contiguous; the correct ids are non-contiguous |

   `clustering` takes the whole v11 hit, dropping 8 → 6; the non-matrix audit
   then removes two more, leaving **4**. Bucket-level clustering numbers rest on
   4 tasks, so a single task swing moves the bucket rate by 25 points — read them
   as indicative only.

2. **Every one of the 30 v11-surviving rubrics changed** (20 of which remain
   after the non-matrix audit). v11 appends an explicit
   all-or-nothing scoring rule to all problems — *"Score 1.0 if the model did not
   cheat AND got the answer correct. Score 0 otherwise"* — replacing wording that
   could be read as awarding credit for passing the anti-cheat check alone. This
   is a grading-semantics change affecting 100% of the subset.

3. **7 question texts changed**: `hb001`, `hb033`, `hb043`, `recvnlq3i6id6qqge`,
   `recaikavdwoimjy3b`, `recnayu0v8zttjlgf`, `recx4bsaa5zoxy3nv`. Mostly filename
   alignment and typo fixes, but `hb033` flipped plural→singular ("list of
   samples" → "a single sample identifier"), which changes the expected answer
   shape.

Several v11 rubric edits **broaden** accepted answers (`hb003` now accepts `F3`
as well as `ITGAV`; `recvnlq3i6id6qqge` accepts "frontal cortex"/"cerebral
cortex"). Those can only move scores up on a re-grade, so a v11 number that is
merely equal to the old one is a real regression.

The pre-v11 corpus and its results are preserved unmodified at
`../../biomysterybench_archive_2026-07-28/`.

## Files

- `problems.csv` — full rows (`bucket` + upstream `id, question, answer_rubric,
  allowed_domains, human_solvable`), ordered by bucket. Grading rubrics included.
- `manifest.csv` — lightweight index (`id, bucket, human_solvable, question_short`)
  for quick filtering / run orchestration.
- `build_expr.py` (in the parent dir) — regenerates both from a fresh upstream
  clone plus the previous release's curation. Rerun it after any upstream bump.
- Data files: extract from `../upstream/data/<id>.zip` into the working directory
  before solving (same convention as the parent benchmark).

## Provenance

Derived from `../upstream/problems.csv`. Task selection is a **manual curation**
by expression-analysis solvability; buckets are TissueAgent skill labels, not part
of the upstream benchmark. Because neither is derivable from upstream metadata,
`build_expr.py` carries the curation forward *by id* and re-attaches it to current
rows — it never invents a bucket for an id it has not seen. v11 added no new
problems (99 → 90 is pure removal), so nothing needed manual triage this time; a
future release that adds problems will require a curation pass before rebuild.

Upstream terms apply: **evaluation only — do not use problem statements, rubrics,
or task formulation for training, fine-tuning, or distillation.** See the parent
[`LICENSE`](../upstream/LICENSE).
