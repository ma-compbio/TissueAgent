# Plan

```yaml
status: recruited
user_request: Generate a spatial scatterplot from dataset_lohoff_et_al_seqfish.h5ad
  where each point is a cell located at its spatial coordinates, colored by cell type
  using colormap.yaml, with an inverted y-axis and overall styling closely matching
  Fig2b.png.
current_step_id: 2
provenance:
  template_names: []
  justification: None of the existing templates (which focus on cell annotation, deconvolution,
    ligand-receptor analysis, enrichment, etc.) are specific to generating a spatial
    scatterplot from an existing annotated dataset. The plan was therefore written
    from scratch following the simple plotting example structure.
```

## Step 1 — Configure and generate spatial scatterplot

```yaml
status: running
assigned_agent: coding_agent
assigned_rationale: This step requires loading an AnnData .h5ad file, reading a YAML
  colormap, and generating a customized spatial scatterplot, which falls squarely
  under the coding_agent’s expertise in spatial transcriptomics data handling and
  plotting; no specialized annotation or deconvolution skills are needed.
skills: []
expected_artifacts:
- tables/lohoff_seqfish_plot_config.tsv
- configs/lohoff_seqfish_colormap_config.json
- figures/lohoff_seqfish_spatial_scatter.png
actual_outputs: []
```

**Description:** Load dataset_lohoff_et_al_seqfish.h5ad and identify the spatial coordinate fields and the cell-type annotation field. Load colormap.yaml and map each cell type to its specified color. Using Fig2b.png as a visual reference, configure point size, alpha, aspect ratio, background, axis limits, and labels, ensuring the y-axis is inverted. Render and save a high-resolution spatial scatterplot where each point is a cell at its spatial location, colored by its cell type according to the colormap.

**Reasoning:** All required actions (data inspection, colormap application, axis inversion, and visual tuning to match the reference) are tightly coupled and culminate in a single figure, so combining them into one step avoids unnecessary fragmentation while still producing all necessary artifacts.
