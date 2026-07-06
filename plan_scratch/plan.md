# Plan

```yaml
status: recruited
user_request: Create a spatial scatterplot from dataset_lohoff_et_al_seqfish.h5ad,
  using colormap.yaml to color cells by cell type, with inverted y-axis, matching
  the style of Fig2b as closely as possible.
current_step_id: 2
provenance:
  template_names: []
  justification: No existing template targets basic spatial plotting with a provided
    colormap and a reference image; the plan was written from scratch for this visualization-only
    task.
```

## Step 1 — Prepare data and generate spatial scatterplot

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: This step involves programmatically loading an h5ad spatial transcriptomics
  file, reading a YAML colormap, and generating a customized matplotlib/scanpy-style
  spatial plot; the coding_agent is best suited for implementing data handling and
  plotting logic, and no specialized CCC or annotation/deconvolution skills are required.
skills: []
expected_artifacts:
- figures/spatial_scatter_celltype_colormap.png
- configs/spatial_scatter_plot_config.json
actual_outputs: []
```

**Description:** Load dataset_lohoff_et_al_seqfish.h5ad and colormap.yaml; identify the spatial coordinate fields (x,y) and per-cell cell-type annotations; map cell types to colors based on the colormap; invert the y-axis; and render a high-resolution scatterplot whose visual style (point size, alpha, background, aspect ratio, margins) closely matches Fig2b.jpg. Save the final figure and a small config file documenting the plotting parameters and colormap used.

**Reasoning:** All tasks—data loading, mapping cell types to colors, axis inversion, and plotting—are tightly coupled and simple enough to perform in one consolidated step while still producing the required figure and a reproducible configuration.
