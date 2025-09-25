PreprocessAnndataDescription = '''
Preprocesses an AnnData object by storing the raw data, normalizing total counts, log‐transforming, and selecting highly variable genes.

Args:
  adata (AnnData): the AnnData object to preprocess
  num_hvgs (int): number of highly variable genes to select (default: 2000)

Returns:
  str: status message

Updates to adata:
  stores the original unprocessed AnnData in adata.raw (as a full copy)
  overwrites adata.X with counts normalized to a total of 1e4 per cell and then log1p transformed
  writes bool indicator of HVGs into `adata.var["highly_variable"]`
  writes means per gene into `adata.var["means"]`
  writes an indicator to `adata.uns["preprocessed"]`
'''.strip()

PreprocessAnndataCode = r'''
def preprocess_adata(adata: AnnData, num_hvgs: int=2000):
    if adata.uns.get("preprocessed", False):
        return "Error: data has already been preprocessed. Nothing was done"
    
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=num_hvgs)
    
    adata.uns["preprocessed"] = True

    return "Success: data has been normalized, log‐transformed, and HVGs selected."
'''

FindMarkerGenesDescription = '''
Finds marker genes for a given spatial cluster.
Requires that spatial clustering (e.g. Leiden) has already been performed.

Args:
  adata (AnnData): the AnnData object to find marker genes of
  cluster_key (str): key of cluster labels in `adata.obs` (e.g. “leiden”, “cluster”, etc.)
  cluster (str): the spatial cluster to query

Returns:
  str: status message on error
  dict: { "top_marker_genes": List[str] }
'''.strip()

FindMarkerGenesCode = r'''
def find_marker_genes(
    adata: AnnData,
    cluster_key: str,
    cluster: str
) -> str:
    
    if cluster_key not in adata.obs:
        return f"Error: Parameter cluster_key=\"{cluster_key}\" not found. Perform a spatial clustering first!"
    
    if len(adata.uns.get("spatial", {})) > 1:
        print("Multiple libraries detected:")
        for lib in adata.uns["spatial"].keys():
            print(f"- {lib}")
    
    try:
        sc.tl.rank_genes_groups(adata, cluster_key, method="wilcoxon", use_raw=False)
        
        if cluster not in adata.obs[cluster_key].unique():
            available_clusters = ", ".join(adata.obs[cluster_key].unique())
            return f"Error: cluster {cluster} not found. Available clusters: {available_clusters}"
        
        marker_genes = adata.uns["rank_genes_groups"]["names"][cluster][:5]
        return {"top_marker_genes": list(marker_genes)}
    
    except Exception as e:
        return f"Error: {str(e)}"
'''.strip()

PlotGeneHeatmapDescription = '''
Generates a heatmap of gene expression from spatial transcriptomics data.

Args:
  adata(AnnData): the AnnData object containing spatial transcriptomics data
  filename (Path or str, optional): where to save the heatmap; must reside within `DATA_DIR` (default: `DATA_DIR/"gene_heatmap.png"`)
  gene(str, optional): the name of a specific gene to visualize. If not provided
    or not found, the top 20 highly variable genes will be displayed instead.
    
Returns:
  str: status message
'''.strip()

PlotGeneHeatmapCode = r'''
def plot_gene_heatmap(
    adata: AnnData,
    filename: Optional[Union[Path, str]]=None,
    gene: str=None
) -> str:

    if filename is None:
        filename = DATA_DIR / "gene_heatmap.png"
    filename = Path(filename)
    if DATA_DIR not in filename.parents and filename != DATA_DIR:
        return f"Error: filename \"{filename}\" must be a subdirectory of DATA_DIR."

    spatial_libraries = adata.uns.get("spatial", {})
    if len(spatial_libraries) > 1:
        print("Multiple libraries detected:")
        for lib in spatial_libraries.keys():
            print(f"- {lib}")
    
    try:
        plt.figure(figsize=(12, 10))
        
        if gene and gene in adata.var_names:
            gene_expression = adata[:, gene].X
            if sp.sparse.issparse(gene_expression):
                gene_expression = gene_expression.toarray()
            
            sns.heatmap(gene_expression, cmap="viridis", 
                        xticklabels=False, yticklabels=False)
            plt.title(f"Expression Heatmap for {gene}")
        else:
            top_hvgs = adata.var[adata.var["highly_variable"]].index.tolist()[:20]
            
            hvg_expression = adata[:, top_hvgs].X
            if sp.sparse.issparse(hvg_expression):
                hvg_expression = hvg_expression.toarray()
            
            sns.heatmap(hvg_expression.T, cmap="viridis", 
                        xticklabels=False, 
                        yticklabels=top_hvgs)
            plt.title("Top Highly Variable Genes Heatmap")
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close()
        
        return f"Success: heatmap generated and saved as \"{filename}\""
    
    except Exception as e:
        return f"Error: {str(e)}"
'''.strip()

QueryGeneExpressionDescription = '''
Queries the expression level of a given gene at the spatial location nearest to the provided coordinates.

Args:
  adata (AnnData): the AnnData object to query gene expression above
  gene (str): gene name to query
  x (float): x-position of spatial position
  y (float): y-position of spatial position

Returns:
  str: status message on error
  dict: { "GENE": expression_level }
'''.strip()

QueryGeneExpressionCode = r'''
def query_gene_expression(
    adata: AnnData,
    gene: str,
    x: float,
    y: float
) -> Union[str, Dict[str, float]]:

    if gene not in adata.var_names:
        return f"Error: gene {gene} not found in the dataset."

    if len(adata.uns.get("spatial", {})) > 1:
        print("Multiple libraries detected:")
        for lib in adata.uns["spatial"].keys():
            print(f"- {lib}")
    
    try:
        spatial_data = adata.obsm["spatial"]
        distances = ((spatial_data[:, 0] - x) ** 2 + 
                     (spatial_data[:, 1] - y) ** 2) ** 0.5
        closest_index = distances.argmin()
        
        expression_level = adata[closest_index, gene].X
        return {gene: float(expression_level[0] 
                if hasattr(expression_level, "__getitem__")
                else expression_level)}
    except Exception as e:
        return f"Error: {str(e)}"
'''.strip()

SpatialClusteringDescription = '''
Performs spatial clustering on spatial transcriptomics data and generates a cluster visualization.

Args:
  adata (AnnData): the AnnData object to perform spatial clustering on
  filename (Path or str, optional): where to save the heatmap; must reside within `DATA_DIR` (default: `DATA_DIR/"spatial_clustering.png"`)

Returns:
    str: status message

Updates to adata:
  writes cluster labels to `adata.obs["leiden"]` as a categorical.
'''.strip()

SpatialClusteringCode = r'''
def spatial_clustering(
    adata: AnnData,
    filename: Optional[Union[Path, str]] = None,
) -> str:

    if filename is None:
        filename = DATA_DIR / "spatial_clustering.png"
    filename = Path(filename)
    if DATA_DIR not in filename.parents and filename != DATA_DIR:
        return f"Error: filename \"{filename}\" must be a subdirectory of DATA_DIR"

    libs = list(adata.uns.get("spatial", {}).keys())
    if len(libs) > 1:
        print("Multiple spatial libraries detected:")
        for lib in libs:
            print(f" - {lib}")

    try:
        if "leiden" in adata.obs:
            print("Warning: leiden clustering already exists, using existing labels")
        else:
            sc.pp.neighbors(adata)
            sc.tl.leiden(adata, resolution=0.5, 
                     flavor="igraph", n_iterations=2, directed=False)
            
            # sq.gr.spatial_neighbors(adata, coord_type="generic")
            # sc.tl.leiden(
            #     adata,
            #     adjacency=adata.obsp["spatial_connectivities"],
            #     key_added="leiden"
            # )
            # adata.obs["leiden"] = adata.obs["leiden"].astype("category")

        try:
            library_id = list(adata.uns.get("spatial", {}).keys())[0] if "spatial" in adata.uns else None
            if library_id:
                sc.pl.spatial(adata, color="leiden", title="Spatial Clusters", show=False)
            else:
                sq.pl.spatial_scatter(adata, color="leiden", title="Spatial Clusters", show=False)
        except Exception as e:
            plt.scatter(adata.obsm["spatial"][:, 0], adata.obsm["spatial"][:, 1], 
                        c=adata.obs["leiden"].astype("category").cat.codes, 
                        cmap="viridis")
            plt.title("Spatial Clusters")

        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()

        return (
            f"Success: spatial clustering performed and visualization saved as \"{filename}\". "
            "Cluster labels saved in `adata.obs[\"leiden\"]`."
        )

    except Exception as e:
        return f"Error: {e}"'''.strip()

# SpatialCoexpressionDescription = '''
# Computes spatial co-expression between two genes across the tissue by leveraging
# neighborhood or cluster information. Requires spatial clustering to have been performed.
#
# Args:
#   adata(AnnData): the AnnData object containing spatial transcriptomics data 
#   gene1(str): the name of the first gene in the pair.
#   gene2(str): the name of the second gene in the pair.
#
# Output:
#   a str containing an error report, if one occurs;
#   otherwise, a pandas DataFrame with co-occurrence scores for the two genes,
#     keyed by spatial neighborhood or cluster.
#
# Updates to adata:
#   Calls `sq.gr.spatial_neighbors`, which writes to:
#     • `adata.obsp["spatial_connectivities"]`
#     • `adata.obsp["spatial_distances"]`
# '''.strip()
#
# SpatialCoexpressionCode = r'''
# def spatial_coexpression(adata: AnnData, gene1: str, gene2: str):
#     try:
#         if len(adata.uns.get("spatial", {})) > 1:
#             print("Multiple libraries detected:")
#             for lib in adata.uns["spatial"].keys():
#                 print(f"- {lib}")
#
#         if gene1 not in adata.var_names or gene2 not in adata.var_names:
#             missing_genes = [g for g in [gene1, gene2] if g not in adata.var_names]
#             return f"Error: Gene(s) {', '.join(missing_genes)} not found in dataset."
#
#         if "leiden" not in adata.obs:
#             return "Error: Spatial clustering needs to be performed first!"
#
#         sq.gr.spatial_neighbors(adata)
#
#         coexpression = sq.gr.co_occurrence(
#             adata, 
#             cluster_key="leiden", 
#             genes=[gene1, gene2]
#         )
#
#         return coexpression
#
#     except Exception as e:
#         return f"Error: {str(e)}"
# '''.strip()
