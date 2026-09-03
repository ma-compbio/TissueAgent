---
name: ccc-data-prep
description: Step 1 of ccc_ensemble. Run the shipped prep script with --adata, --cell-type and --species; it writes ccc_base.h5ad, ccc_lr_common.csv and logs/ccc_data_prep.json for all later members.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing, ensemble, progeny, decoupler]
status: enable
---

# CCC — shared data prep

Fast path: run this command directly; do not list/read the skill directory or script, paste code, or create extra verification files.

```python
%run project/skills/ccc-data-prep/scripts/ccc_data_prep.py --adata <path.h5ad> --cell-type <obs column> --species <human|mouse>
```

Required outputs: `project/outputs/ccc_base.h5ad`, `project/outputs/ccc_lr_common.csv`, `project/outputs/logs/ccc_data_prep.json`. If a file tool is needed, use `/project/...` paths (not `workspace/project/...`).
