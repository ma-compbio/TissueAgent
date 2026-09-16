###  Cell neighborhood network construction. 
To construct a cell neighborhood
network, for each cell within a given embryo and z slice, we extracted the
polygon representation of the cell’s segmentation corresponding to a set of vertex
coordinates. We then calculated an expanded segmentation by constructing a new
polygon where each expanded vertex was lengthened along the line containing
the original vertex and the center of the polygon. We performed a multiplicative
expansion of 1.3 for each vertex. To construct the cell neighborhood network,
we then identified the other cells in which segmentation vertices were found to
be within the expanded polygon. Cell neighborhood networks were considered
separately for each embryo and z slice combination.

### Cell–cell contact map inference. 
We constructed cell–cell contact maps for multiple
cell annotation labelings, including mapped cell types, subclusters within each
cell type and mapped gut tube subtypes. To do this, for each embryo and z
slice combination, we extracted the cell neighborhood network and cell-level
annotation. We then generated cell–cell contact maps by first calculating the
number of edges for which a particular pair of annotated groups was observed.
We then randomly reassigned (500 times) the annotation by sampling without
replacement and calculated the number of edges for all pairs of annotated groups.
To construct the cell–cell contact map, we reported the proportion of times the
randomly reassigned number of edges was larger than or equal to the observed
number of edges. Small values correspond to the pair of annotation groups being
more segregated, and large values correspond to them being more integrated in
physical space than a random allocation. To combine these cell–cell contact maps
for each embryo and z slice combination, we further calculated the element-wise
mean for each pair of cell labels. We visualized this in a heat map, ordering the
annotation groups using hierarchical clustering with Euclidean distance and
complete linkage. In the case of the gut tube subtypes, we ordered these classes by
the anterior–posterior ordering given by Nowotschin et al.2. In the brain subtypes,
we ordered these classes by their approximate anatomical location, from the
forebrain to the hindbrain region.



<!-- ### Cell–cell contact map inference -->
<!-- 
Construct cell–cell contact maps using `obs['celltype_mapped_refined']` as the annotation and
`obsm['spatial']` as the cell coordinates. Parse embryo and *z* slice identity from observation names
of the form `embryo<id>_Pos<position>_cell<id>_z<slice>`. Exclude cells annotated as `Low quality`,
because that category is absent from the target panel.

For each embryo and *z* slice combination, extract the cell-neighborhood network. The provided H5AD
does not contain a stored neighborhood graph, so reconstruct it reproducibly as an undirected,
symmetric 10-nearest-neighbor graph from the spatial coordinates within that embryo/*z*-slice
stratum. Remove self-edges and count each undirected edge once. Record this graph reconstruction as
a dataset-driven fallback in the output methodology report.

For each unordered pair of cell-type labels \((a,b)\), calculate the observed number of graph edges
\(C_{ab}^{\mathrm{obs}}\) joining those labels. Randomly reassign the cell-type annotations within the
same embryo/*z*-slice stratum by sampling without replacement, preserving the label counts. Repeat
this permutation 500 times using a fixed, reported random seed. For each pair, report

\[
p_{ab} = \frac{1}{500}\sum_{r=1}^{500}
\mathbf{1}\!\left(C_{ab}^{(r)} \ge C_{ab}^{\mathrm{obs}}\right).
\]

Small values correspond to annotation groups that are more spatially segregated than expected under
random allocation; large values correspond to groups that are more spatially integrated. Retain the
number of contributing strata for every pair and use available-stratum means when a pair is not
represented in every stratum.

Combine the contact maps across embryo/*z*-slice combinations by calculating the elementwise mean for
each pair of cell labels. Apply hierarchical clustering to the resulting symmetric mean contact map,
using Euclidean distance and complete linkage, and use the same ordering for rows and columns.

Visualize the clustered result as a lower-triangular heat map with matching row and column
dendrograms, diagonal cell-type labels, and cell-type annotation strips. Include a horizontal scale
labelled `Integrated` at the large-value end and `Segregated` at the small-value end. Save the mean
matrix, per-stratum matrices, pair-support counts, clustering order/linkage, permutation settings,
and a concise methodology/QC report alongside the final figure. -->
