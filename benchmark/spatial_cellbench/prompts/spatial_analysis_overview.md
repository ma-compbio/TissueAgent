## Dimensionality Reduction

Purpose: Represent high-dimensional gene expression in fewer dimensions for exploration and
visualization. Use the reduced representation to summarize major expression patterns, compare
observations, and relate those patterns back to their tissue locations.

## Spatial Neighborhood Graph Construction

Purpose: Build a neighborhood graph from physical tissue coordinates as input for spatial
analyses and visualization. Connect nearby observations using an appropriate distance or
neighborhood rule, and examine how sensitive downstream results are to the neighborhood scale.

## Spatial Domain Identification

Purpose: Identify spatially coherent tissue domains with shared expression patterns. Use both
molecular similarity and spatial adjacency, explore domain granularity, and assign a domain
label to each spatial observation for downstream interpretation.

## Trajectory and Pseudotime Analysis

Purpose: Model continuous developmental, differentiation, or state transitions when supported
by the study context. Infer an ordering or coarse progression from expression patterns, then
assess how the inferred trajectory is arranged across tissue space and whether neighboring
observations show smooth transitions.

## Differential Expression and Marker Gene Detection

Purpose: Identify genes that distinguish spatial domains, tissue regions, or stated experimental
conditions. Perform suitable group-wise or pairwise comparisons, report effect sizes and
uncertainty with multiple-testing control, and summarize marker genes for each relevant group.

## Gene Signature Scoring

Purpose: Quantify the expression of biologically motivated gene sets for each spatial
observation. Compare signature scores across spatial domains or stated conditions and map their
spatial distributions to identify localized or graded activity patterns.

## Visualization

Purpose: Visualize expression structure and analysis results in tissue space. Plot domain labels,
genes, signatures, trajectories, and metadata on spatial coordinates; complement these maps with
reduced-dimension plots and concise distribution or matrix views that support interpretation.
