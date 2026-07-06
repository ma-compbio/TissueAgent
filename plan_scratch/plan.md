# Plan

```yaml
status: done
user_request: Plot a spatial scatterplot from dataset_lohoff_et_al_seqfish.h5ad with
  cells positioned by spatial coordinates, colored by cell type using colormap.yaml,
  with inverted y-axis, matching Fig2b.png style.
current_step_id: 2
provenance:
  template_names: []
  justification: None of the existing templates (which focus on annotation, deconvolution,
    ligand-receptor analysis, enrichment, etc.) apply to a simple spatial scatterplot
    generation task, so this plan was written from scratch.
```

## Step 1 — Generate spatial cell-type scatterplot

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: This step requires loading an h5ad spatial dataset and colormap,
  then generating a spatial scatterplot that closely matches a reference figure; the
  coding_agent is ideal for custom plotting from AnnData, and the figure-reproduce
  skill is specifically designed to recreate published-style figures as faithfully
  as possible.
skills:
- figure-reproduce
expected_artifacts:
- tables/colormap_resolved.tsv
- figures/spatial_scatter_celltype_like_Fig2b.png
actual_outputs: []
```

**Description:** Load dataset_lohoff_et_al_seqfish.h5ad and colormap.yaml; identify the spatial coordinate fields and the cell-type annotation; map each cell type to its specified color; then plot a scatterplot where each point is a cell at its spatial location, colored by cell type, with the y-axis inverted and overall style (point size, aspect ratio, background, axis visibility) tuned to closely match Fig2b.png.

**Reasoning:** All required operations—from reading inputs to rendering the final figure—are straightforward and tightly coupled, so combining them into a single step avoids unnecessary fragmentation while still producing the requested visualization artifact.
