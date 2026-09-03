# Optimizer CCC benchmark

Measures whether the knowledge optimizer (`tissueagent optimize`) actually
improves TissueAgent over rounds: runs start from a deliberately **minimal**
`ccc_ensemble` plan template, and each round's sessions feed one optimization
round that edits the knowledge layer. Expected trend: accuracy up, tokens down.

## Ground truth

Accuracy is agreement with an **expert reference run**: the same frozen
`ccc-*` skill scripts executed directly (no agent) on the same pinned input.
Metrics per run: Spearman of `ensemble_score` over the common LR universe,
top-20 Jaccard, validity of the output contract; plus tokens/replans from
`metrics.json`. The optimizer never sees the reference tables — only agent
sessions and scores — so it can only improve process, not memorize answers.

## Datasets (pinned inputs staged into workspace/library/datasets/)

| name | staged file | species | labels |
|---|---|---|---|
| lymph_node | `opt_ccc_lymph_node.h5ad` | human Visium | `domain` (KMeans k=8, seed 1337 — file ships unlabeled) |
| dlpfc | `opt_ccc_dlpfc_151673.h5ad` | human Visium, section 151673 | `layer` (Maynard laminar annotations) |
| merfish | `opt_ccc_merfish.h5ad` | mouse MERFISH, Animal 1 / Bregma −0.14 | `Cell_class` (classes <10 cells dropped) |

Agent and reference consume byte-identical inputs, so score deltas are
attributable to the knowledge layer, not to input divergence.

## Workflow

```bash
# one-time setup
python benchmark/optimizer_ccc/prepare_inputs.py      # stage pinned inputs
python benchmark/optimizer_ccc/make_reference.py      # expert references (commit these)

# the benchmark loop (needs a committed knowledge/ tree)
python benchmark/optimizer_ccc/run_benchmark.py --rounds 3 --repeats 1
```

`run_benchmark.py` flips the full `ccc_ensemble.md` to disabled and the minimal
`ccc_ensemble_minimal.md` to enabled for the duration (git-committed both ways,
restored on exit even on crash). Per round it writes
`runs/<ts>/round_N/{<dataset>_<rep>/session/, results.json, optimizer_focus.md}`
and appends to `runs/<ts>/summary.csv`
(round, valid_run_rate, mean_spearman, mean_topk_jaccard, median_total_tokens,
knowledge_commit) — the expected-trend table.

Each optimizer round is a normal `tissueagent optimize` invocation; its edits
and report are committed by the optimizer itself (`optimizer_reports/`), and
`summary.csv` records the knowledge commit per round so any round's knowledge
state can be checked out and inspected.
