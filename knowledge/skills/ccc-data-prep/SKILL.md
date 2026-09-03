---
name: ccc-data-prep
description: Step 1 of the ccc_ensemble workflow. Runs the shipped prep script that preprocesses a spatial transcriptomics AnnData once into an immutable base object (log1p .X, `_ct` labels, native-unit spatial coords), computes the PROGENy per-cell downstream-response amplitude (on the FULL transcriptome, before gene-slimming) into obs['_dact'], and builds the ONE shared monomeric ligand-receptor resource all four members (LIANA+, COMMOT, stLearn, decoupler) run on. Emits ccc_base.h5ad, ccc_lr_common.csv, and a calibration log.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing, ensemble, progeny, decoupler]
status: enable
---

# CCC — shared data prep

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-data-prep/scripts/ccc_data_prep.py --adata <path.h5ad> --cell-type <obs column> --species <human|mouse>
```

Outputs: `project/outputs/ccc_base.h5ad`, `project/outputs/ccc_lr_common.csv`,
`project/outputs/logs/ccc_data_prep.json`.
