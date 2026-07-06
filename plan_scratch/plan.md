# Plan

```yaml
status: recruited
user_request: Open library/datasets/refset.h5ad and report only its (n_cells, n_genes)
  shape without generating plots or additional user-facing files.
current_step_id: 2
provenance:
  template_names: []
  justification: This is a simple single-file inspection task that does not match
    any of the multi-step analysis templates, so the plan was written from scratch.
```

## Step 1 — Load H5AD and record matrix shape

```yaml
status: running
assigned_agent: coding_agent
assigned_rationale: This step requires loading an H5AD file and extracting its matrix
  shape using Python/R, which falls directly under the coding_agent’s capabilities,
  and the user explicitly requested the coding agent.
skills: []
expected_artifacts:
- tables/refset_shape.json
actual_outputs:
- project/outputs/tables/refset_shape.json
```

**Description:** Use an appropriate library to load library/datasets/refset.h5ad, extract the number of observations (cells) and variables (genes) from the main data matrix, and save these two integers in a minimal text or JSON artifact to be reported back to the user.

**Reasoning:** The user only needs the dataset dimensions, so a single execution step that reads the H5AD file and extracts its shape is sufficient; a tiny artifact ensures the result is explicitly captured for downstream reporting.
