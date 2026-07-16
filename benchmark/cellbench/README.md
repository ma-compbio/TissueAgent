# CellBench three-arm comparison

This benchmark compares three analysis-planning strategies on the 50 public
paper contexts in CellVoyager's CellBench dataset. Generation sees only each
paper's background; the hidden analyses are exposed afterward to an independent,
arm-blind judge using strict one-to-one matching.

## Arms

- `tissueagent`: a standalone TissueAgent-style planner, critic, and revision
  adapter. It does not execute the full TissueAgent graph.
- `cellvoyager`: CellVoyager-style planning using its public analysis overview.
- `combined`: the CellVoyager draft revised by the TissueAgent-style critic.

Each arm returns five proposals with an equal logical budget of three calls.
Because the CV draft is shared with Combined, each paper uses eight unique
generation calls and three judge calls. Generation used GPT-5.1 with high
reasoning; judging used GPT-5 with high reasoning.

## Results

| Arm | Precision@5 | GT recall@5 | F1@5 | Paper hit rate |
|---|---:|---:|---:|---:|
| TissueAgent-style | 0.6880 ± 0.0160 | 0.3880 ± 0.0120 | 0.4867 ± 0.0141 | 0.9400 ± 0.0000 |
| CellVoyager | 0.7080 ± 0.0312 | 0.3867 ± 0.0186 | 0.4904 ± 0.0232 | 1.0000 ± 0.0000 |
| Combined | **0.7373 ± 0.0151** | **0.4053 ± 0.0076** | **0.5131 ± 0.0099** | 1.0000 ± 0.0000 |

Values are mean ± sample SD across three stochastic replicates. Replicate F1
values for TissueAgent-style / CellVoyager / Combined were:

- replicate 1: 0.4870 / 0.5007 / 0.5197
- replicate 2: 0.5007 / 0.4638 / 0.5017
- replicate 3: 0.4724 / 0.5066 / 0.5177

The mean paired Combined F1 delta is +0.0227 versus CellVoyager and +0.0263
versus TissueAgent-style. On the common-clean sensitivity subset, which removes
the union of papers affected by provider safety handling and retains the same 32
papers in every replicate, the deltas remain +0.0244 and +0.0215.

These results support a repeatable benefit from applying the TissueAgent-style
critic/reviser to CellVoyager plans. The advantage over the standalone
TissueAgent-style arm is smaller and more stochastic. Three replicates and an
LLM judge do not establish statistical significance, and this benchmark does not
measure full data analysis or full TissueAgent graph execution.

Machine-readable metadata, replicate summaries, the aggregate, and the safety
sensitivity analysis are in [`results/`](results/). The 150 raw checkpoints are
intentionally excluded from git.

## Reproduce

Set `OPENAI_API_KEY` in the project environment, then run:

```bash
python demo/run_cellbench_comparison.py \
  --replicates 3 \
  --workers 4 \
  --run-dir benchmark/cellbench/runs/my_run
```

Runtime outputs under `benchmark/cellbench/runs/` are ignored by git.
