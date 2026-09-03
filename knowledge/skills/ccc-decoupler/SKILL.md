---
name: ccc-decoupler
description: Step 5 of the ccc_ensemble workflow. The downstream-response member. Runs the shipped run_decoupler scorer, scoring each shared-resource LR pair by whether its actively-receiving cells (receptor present AND ligand arriving over a kNN graph) co-locate with the PROGENy downstream response amplitude computed in ccc-data-prep (obs['_dact']). Writes decoupler_scores.csv for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, decoupler, progeny, downstream, pathway, ensemble]
status: enable
---

# CCC — decoupler + PROGENy (downstream-response axis)

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-decoupler/scripts/ccc_decoupler.py
```

Reads the Step 1 artifacts from `project/outputs/`; writes `project/outputs/decoupler_scores.csv`.
