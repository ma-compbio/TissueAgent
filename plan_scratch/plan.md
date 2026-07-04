# Plan

```yaml
status: recruited
user_request: Create a spatial scatterplot from the dataset in datasets/ colored by
  cell type
current_step_id: 2
provenance:
  template_names: []
  justification: Existing templates focus on cell annotation, deconvolution, or complex
    analysis rather than simple visualization; a custom one-step plotting plan is
    more appropriate.
```

## Step 1 — Load dataset and generate spatial plot

```yaml
status: running
assigned_agent: coding_agent
assigned_rationale: This step requires loading a spatial transcriptomics dataset from
  disk, identifying spatial coordinate and cell-type columns, and generating a scatterplot,
  which falls squarely within the coding_agent’s strengths in Python/R-based spatial
  transcriptomics analysis and visualization.
skills: []
expected_artifacts:
- tables/data_inventory.tsv
- tables/spatial_plot_config.json
- figures/spatial_scatter_by_cell_type.png
actual_outputs: []
```

**Description:** Load the spatial transcriptomics dataset from the datasets/ directory, detect the columns that contain spatial coordinates and cell-type annotations, and generate a 2D scatterplot of spatial positions colored by cell type. Save both the plotting configuration and the resulting figure.

**Reasoning:** All required actions—data loading, identifying coordinate and annotation fields, and plotting—are tightly coupled and simple enough to be executed in a single step.
