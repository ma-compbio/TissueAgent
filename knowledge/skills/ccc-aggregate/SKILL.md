---
name: ccc-aggregate
description: Final ccc_ensemble step. Run the shipped aggregator; it inner-joins the four member score tables and writes project/outputs/ccc_ensemble.csv.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, ensemble, consensus]
status: enable
---

# CCC — Ensemble (mean-of-percentile-ranks consensus)

Fast path: run this command directly; do not list/read the skill directory or script, paste code, change the combiner, or create extra verification files.

```python
%run project/skills/ccc-aggregate/scripts/ccc_aggregate.py
```

Reads the four `*_scores.csv` tables; required output: `project/outputs/ccc_ensemble.csv`. If a file tool is needed, use `/project/...` paths.
