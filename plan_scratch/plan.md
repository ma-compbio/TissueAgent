# Plan

```yaml
status: done
user_request: Create a spatial scatterplot from dataset_lohoff_et_al_seqfish.h5ad
  with cells colored by cell type using colormap.yaml, inverted y-axis, and styling
  similar to Fig2b.png
current_step_id: 2
provenance:
  template_names: []
  justification: This is a focused plotting task that does not match any of the multi-step
    analysis templates (which target enrichment, deconvolution, cell-cell communication,
    etc.), so a custom single-step plan is more appropriate.
```

## Step 1 — Generate styled spatial cell-type scatterplot

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: This step requires loading an h5ad spatial transcriptomics dataset,
  applying a custom colormap from YAML, and generating a spatial scatter plot that
  closely matches a reference figure; the coding_agent is best suited for this kind
  of data-driven plotting task, and the figure-reproduce skill is explicitly designed
  to recreate figures to match a provided reference.
skills:
- figure-reproduce
expected_artifacts:
- figures/lohoff_seqfish_celltype_spatial_scatter.png
actual_outputs: []
```

**Description:** Load dataset_lohoff_et_al_seqfish.h5ad to extract per-cell spatial coordinates and cell-type annotations, and load colormap.yaml to map cell types to specific colors. Use these to render a spatial scatterplot where each point’s (x, y) position corresponds to its spatial location, color corresponds to its cell type, and the y-axis is inverted. Adjust point size, aspect ratio, background, and axis visibility to visually match Fig2b.png as closely as possible, then save the final plot.

**Reasoning:** All required actions—data loading, mapping cell types to colors, configuring plot aesthetics, and saving the figure—are tightly coupled and can be accomplished in a single coherent execution step without unnecessary intermediate stages.
