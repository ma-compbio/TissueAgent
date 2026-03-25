### Spatial heterogeneity testing per cell type

We identified genes with a spatially heterogeneous pattern of expression using a linear model with observations corresponding to each cell for a given cell type and with outcome corresponding to the gene of interest’s expression value. For each gene, we fit a linear model including the embryo and *z* slice information as covariates as well as an additional covariate corresponding to the weighted mean of all other cells’ gene expression values. The weight was computed as the inverse of the cell–cell distance in the cell–cell neighborhood network.

More formally, let \( x_{ij} \) be the expression of gene \( i \) for cell \( j \). Calculate \( x^{*}_{ij} \) as the weighted average of other \( K \) cells’ expression weighted by distance in the neighborhood network:

\[
x^{*}_{ij} = \sum_{k \in K} \frac{x_{ik}}{D_{jk}}
\]

where

\[
D_{jk} = d(v_j, v_k)
\]

is the path length in the neighborhood network between vertices corresponding to cells \( j \) and \( k \).

We then fit the linear model for each gene:

\[
x_i = \beta_0 + \beta_1 x_i^{*} + \beta_2 e + \beta_3 z + \beta_4 e \times z + \epsilon .
\]

Here, \( e \) and \( z \) correspond to the embryo and *z* slice identity of the cells, respectively, and \( \epsilon \) represents random normally distributed noise. The *t*-statistic corresponding to \( \beta_1 \) is reported here as a measure of spatial heterogeneity for the given gene, a large value corresponding to a strong spatial expression pattern of the gene in space, especially among its neighbors.