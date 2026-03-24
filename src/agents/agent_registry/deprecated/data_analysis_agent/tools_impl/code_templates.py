# src/tools/code_templates.py
# Template code examples for spatial transcriptomics analysis

# This file provides code templates that the data_analysis agent can reference
# when generating custom code for spatial transcriptomics analysis tasks.

# 1. Spatially Variable Gene Analysis
SVG_ANALYSIS_TEMPLATE = """
# Spatially Variable Gene Analysis
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Basic preprocessing (if needed)
# sc.pp.normalize_total(adata, target_sum=1e4)
# sc.pp.log1p(adata)

# Calculate spatial neighbors
print("Computing spatial neighbors...")
sq.gr.spatial_neighbors(adata, n_neighs=6)

# Compute spatially variable genes using Moran's I
print("Finding spatially variable genes...")
sq.gr.spatial_autocorr(
    adata,
    mode="moran",  # Options: "moran", "geary", or "hotspot"
    n_perms=100,   # Number of permutations for significance testing
    n_jobs=-1      # Use all available cores
)

# Get results and find top spatially variable genes
moran_scores = adata.uns["moranI"]
top_genes = moran_scores.head(20)  # Adjust number as needed
print(f"Top spatially variable genes:\\n{top_genes}")

# Visualize spatial expression patterns of top genes
fig, axs = plt.subplots(2, 3, figsize=(15, 10))
axs = axs.flatten()

for i, gene in enumerate(top_genes.index[:6]):
    if i < len(axs) and gene in adata.var_names:
        sq.pl.spatial_scatter(
            adata,
            color=gene,
            size=1.5,
            title=f"{gene} (Moran's I = {moran_scores.loc[gene][0]:.4f})",
            ax=axs[i],
            show=False
        )

plt.tight_layout()
plt.savefig("top_spatially_variable_genes.png", dpi=300)
plt.close()

print("Analysis complete. Top spatially variable genes visualized in 'top_spatially_variable_genes.png'")
"""

# 2. Clustering and Cell Type Analysis
CLUSTERING_TEMPLATE = """
# Clustering and Cell Type Analysis
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Basic preprocessing (if needed)
# sc.pp.normalize_total(adata, target_sum=1e4)
# sc.pp.log1p(adata)
# sc.pp.highly_variable_genes(adata, n_top_genes=2000)

# Compute PCA
print("Computing PCA...")
sc.pp.pca(adata)

# Compute neighborhood graph
print("Computing neighborhood graph...")
sc.pp.neighbors(adata, n_neighbors=15)

# Cluster cells using Leiden algorithm
print("Clustering cells...")
sc.tl.leiden(adata, resolution=0.5)  # Adjust resolution to control number of clusters

# Visualize clusters on spatial coordinates
fig, ax = plt.subplots(figsize=(10, 10))
sc.pl.spatial(
    adata,
    color="leiden",
    spot_size=50,  # Adjust based on your data
    title="Spatial Clusters (Leiden, res=0.5)",
    ax=ax,
    show=False
)
plt.tight_layout()
plt.savefig("spatial_clusters.png", dpi=300)
plt.close()

# Count number of spots in each cluster
cluster_counts = adata.obs['leiden'].value_counts()
print("Spots per cluster:")
print(cluster_counts)

# Find marker genes for each cluster
print("Finding marker genes for each cluster...")
sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')

# Create marker gene heatmap
sc.pl.rank_genes_groups_heatmap(
    adata, 
    n_genes=5,  # Top 5 genes per cluster
    show=False
)
plt.savefig("cluster_marker_genes_heatmap.png", dpi=300)
plt.close()

# Create dotplot of marker genes
sc.pl.rank_genes_groups_dotplot(
    adata,
    n_genes=5,
    show=False
)
plt.savefig("cluster_marker_genes_dotplot.png", dpi=300)
plt.close()

print("Clustering analysis complete. Results visualized in PNG files.")
"""

# 3. Ligand-Receptor Interaction Analysis
LIGREC_TEMPLATE = """
# Ligand-Receptor Interaction Analysis
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Make sure we have clusters
if 'leiden' not in adata.obs:
    print("Clustering data first...")
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata)

# Perform ligand-receptor analysis
print("Analyzing ligand-receptor interactions...")
sq.gr.ligrec(
    adata,
    cluster_key="leiden",  # Column with cluster assignments
    species="human",       # "human" or "mouse"
    n_perms=100,           # Number of permutations for significance testing
)

# Extract significant interactions
if "ligrec" in adata.uns and "pvalues" in adata.uns["ligrec"]:
    sig_mask = adata.uns["ligrec"]["pvalues"] < 0.05
    
    # Create DataFrame with significant interactions
    interactions = pd.DataFrame({
        "source_cluster": adata.uns["ligrec"]["source"][sig_mask],
        "target_cluster": adata.uns["ligrec"]["target"][sig_mask],
        "ligand": adata.uns["ligrec"]["ligand"][sig_mask],
        "receptor": adata.uns["ligrec"]["receptor"][sig_mask],
        "pvalue": adata.uns["ligrec"]["pvalues"][sig_mask]
    })
    
    # Save to CSV
    interactions.to_csv("ligand_receptor_interactions.csv", index=False)
    
    # Print summary
    print(f"Found {len(interactions)} significant ligand-receptor interactions")
    print(interactions.head(10))  # Show top 10
    
    # Count interactions by source cluster
    source_counts = interactions['source_cluster'].value_counts()
    
    # Visualize interaction network
    sq.pl.ligrec(
        adata,
        cluster_key="leiden",
        source_groups="all",  # Can specify specific source clusters
        target_groups="all",  # Can specify specific target clusters
        figsize=(12, 10),
        show=False
    )
    plt.savefig("ligand_receptor_interactions.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Ligand-receptor analysis complete. Results saved to 'ligand_receptor_interactions.csv' and visualized in 'ligand_receptor_interactions.png'")
else:
    print("Ligand-receptor analysis failed or found no significant interactions.")
"""

# 4. Gene Expression Visualization
GENE_EXPRESSION_TEMPLATE = """
# Spatial Gene Expression Visualization
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Define genes of interest to visualize
genes_of_interest = ["VEGFA", "CD68", "PDGFRA"]  # Replace with your genes

# Check which genes are present in the dataset
valid_genes = [gene for gene in genes_of_interest if gene in adata.var_names]

if not valid_genes:
    print(f"None of the specified genes {genes_of_interest} found in dataset.")
else:
    # Create a multi-panel figure
    n_genes = len(valid_genes)
    n_cols = min(3, n_genes)
    n_rows = (n_genes + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 5*n_rows))
    
    # Handle single gene case
    if n_genes == 1:
        axes = np.array([axes])
    
    # Flatten for easier indexing
    axes = axes.flatten()
    
    # Plot each gene
    for i, gene in enumerate(valid_genes):
        if i < len(axes):
            sq.pl.spatial_scatter(
                adata,
                color=gene,
                size=1.5,
                title=f"{gene} expression",
                ax=axes[i],
                cmap="viridis",
                show=False
            )
    
    # Hide unused axes
    for i in range(n_genes, len(axes)):
        axes[i].axis('off')
    
    plt.tight_layout()
    plt.savefig("spatial_gene_expression.png", dpi=300)
    plt.close()
    
    print(f"Visualized spatial expression of {n_genes} genes. Results saved to 'spatial_gene_expression.png'")
    
    # Optional: Create additional visualizations if clusters are available
    if 'leiden' in adata.obs:
        sc.pl.dotplot(
            adata,
            var_names=valid_genes,
            groupby='leiden',
            show=False
        )
        plt.savefig("gene_expression_by_cluster.png", dpi=300)
        plt.close()
        
        print("Also created dotplot showing expression by cluster in 'gene_expression_by_cluster.png'")
"""

# 5. Spatial Domain Identification
SPATIAL_DOMAIN_TEMPLATE = """
# Spatial Domain Identification
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Calculate spatial neighbors
print("Computing spatial neighbors...")
sq.gr.spatial_neighbors(adata)

# Find spatially variable genes
print("Identifying spatially variable genes...")
sq.gr.spatial_autocorr(
    adata,
    mode='moran',
    n_perms=100
)

# Get top spatially variable genes for domain detection
top_svgs = list(adata.uns['moranI'].head(100).index)
top_svgs = [g for g in top_svgs if g in adata.var_names]

if not top_svgs:
    print("No spatially variable genes found!")
else:
    print(f"Using {len(top_svgs)} spatially variable genes for domain detection")
    
    # Create a subset with the top spatially variable genes
    adata_subset = adata[:, top_svgs].copy()
    
    # Calculate neighborhood graph
    sc.pp.neighbors(adata_subset)
    
    # Identify spatial domains using Leiden clustering with appropriate resolution
    sc.tl.leiden(adata_subset, resolution=0.5, key_added='spatial_domain')
    
    # Transfer domain assignments back to original adata
    adata.obs['spatial_domain'] = adata_subset.obs['spatial_domain']
    
    # Visualize the spatial domains
    fig, ax = plt.subplots(figsize=(10, 8))
    sc.pl.spatial(adata, color='spatial_domain', ax=ax, show=False)
    plt.tight_layout()
    plt.savefig("spatial_domains.png", dpi=300)
    plt.close()
    
    # Find marker genes for each domain
    sc.tl.rank_genes_groups(adata, 'spatial_domain', method='wilcoxon')
    
    # Extract top markers for each domain
    domain_markers = {}
    for domain in adata.obs['spatial_domain'].unique():
        domain_markers[domain] = sc.get.rank_genes_groups_df(
            adata, group=domain
        ).head(5)['names'].tolist()
        
        print(f"Domain {domain} markers: {domain_markers[domain]}")
    
    # Visualize domain markers in a heatmap
    sc.pl.rank_genes_groups_heatmap(
        adata, 
        groupby='spatial_domain',
        n_genes=3,   # Top 3 genes per domain
        show=False
    )
    plt.savefig("domain_markers_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Spatial domain analysis complete. Results saved to 'spatial_domains.png' and 'domain_markers_heatmap.png'")
"""

# 6. Comprehensive Analysis Pipeline
COMPREHENSIVE_ANALYSIS_TEMPLATE = """
# Comprehensive Spatial Transcriptomics Analysis
import scanpy as sc
import squidpy as sq
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

print(f"Data shape: {adata.shape}")

# ===== 1. Preprocessing =====
print("Preprocessing data...")
# Quality control and filtering
sc.pp.calculate_qc_metrics(adata, inplace=True)
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# Normalize and log-transform
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Find highly variable genes
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
adata.raw = adata  # Store normalized counts
adata = adata[:, adata.var.highly_variable]  # Subset to highly variable genes

# Dimensionality reduction
sc.pp.pca(adata)

# ===== 2. Neighborhood Graphs =====
print("Computing neighborhood graphs...")
# Expression-based neighborhood graph
sc.pp.neighbors(adata, n_neighbors=15)

# Spatial neighborhood graph
sq.gr.spatial_neighbors(adata, coord_type="generic")

# ===== 3. Clustering =====
print("Performing clustering...")
# Cluster cells
sc.tl.leiden(adata, resolution=0.5)

# Visualize clusters spatially
fig, ax = plt.subplots(figsize=(10, 8))
sc.pl.spatial(adata, color="leiden", ax=ax, show=False)
plt.savefig("spatial_clusters.png", dpi=300)
plt.close()

# ===== 4. Find Marker Genes =====
print("Finding marker genes...")
# Find markers for each cluster
sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")

# Create marker gene heatmap
sc.pl.rank_genes_groups_heatmap(
    adata, n_genes=5, groupby="leiden", show=False
)
plt.savefig("marker_genes_heatmap.png", dpi=300, bbox_inches='tight')
plt.close()

# ===== 5. Spatially Variable Genes =====
print("Finding spatially variable genes...")
# Find spatially variable genes
sq.gr.spatial_autocorr(
    adata,
    mode="moran",
    n_perms=100,
    n_jobs=-1
)

# Get top spatially variable genes
top_svgs = adata.uns["moranI"].head(20).index.tolist()
print(f"Top spatially variable genes: {top_svgs[:5]}...")

# Visualize top spatially variable genes
fig, axs = plt.subplots(2, 3, figsize=(15, 10))
axs = axs.flatten()

for i, gene in enumerate(top_svgs[:6]):
    if gene in adata.var_names:
        sq.pl.spatial_scatter(adata, color=gene, ax=axs[i], show=False)

plt.tight_layout()
plt.savefig("spatially_variable_genes.png", dpi=300)
plt.close()

# ===== 6. Neighborhood Enrichment =====
print("Analyzing spatial relationships between clusters...")
# Analyze spatial relationships between clusters
sq.gr.nhood_enrichment(adata, cluster_key="leiden")

# Visualize neighborhood enrichment
fig, ax = plt.subplots(figsize=(10, 8))
sq.pl.nhood_enrichment(adata, cluster_key="leiden", ax=ax, show=False)
plt.savefig("neighborhood_enrichment.png", dpi=300)
plt.close()

# ===== 7. Ligand-Receptor Analysis =====
print("Analyzing potential cell-cell communication...")
# Analyze potential cell-cell communication
sq.gr.ligrec(adata, cluster_key="leiden")

# ===== 8. Visualization Summary =====
print("Creating summary visualization...")
# Create a comprehensive figure
fig, axs = plt.subplots(2, 2, figsize=(15, 15))

# Clusters
sc.pl.spatial(adata, color="leiden", ax=axs[0, 0], show=False)
axs[0, 0].set_title("Spatial Clusters")

# Top SVG
if len(top_svgs) > 0 and top_svgs[0] in adata.var_names:
    sq.pl.spatial_scatter(adata, color=top_svgs[0], ax=axs[0, 1], show=False)
    axs[0, 1].set_title(f"Top Spatially Variable Gene: {top_svgs[0]}")

# UMAP with clusters
sc.tl.umap(adata)
sc.pl.umap(adata, color="leiden", ax=axs[1, 0], show=False)
axs[1, 0].set_title("UMAP Embedding")

# Neighborhood enrichment
sq.pl.nhood_enrichment(adata, cluster_key="leiden", ax=axs[1, 1], show=False)
axs[1, 1].set_title("Spatial Neighborhood Enrichment")

plt.tight_layout()
plt.savefig("analysis_summary.png", dpi=300)
plt.close()

print("Comprehensive spatial transcriptomics analysis complete.")
print("Visualizations saved as PNG files.")
"""

# 7. Preprocessing Template
PREPROCESSING_TEMPLATE = """
# Preprocessing for Spatial Transcriptomics Data
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

print(f"Original data shape: {adata.shape}")

# 1. Quality control and filtering
print("Calculating QC metrics...")
sc.pp.calculate_qc_metrics(adata, inplace=True)

# Filter cells by minimum genes expressed
min_genes = 200
print(f"Filtering spots with fewer than {min_genes} genes detected...")
sc.pp.filter_cells(adata, min_genes=min_genes)

# Filter genes by minimum cells expressed in
min_spots = 3
print(f"Filtering genes detected in fewer than {min_spots} spots...")
sc.pp.filter_genes(adata, min_cells=min_spots)

print(f"Data shape after basic filtering: {adata.shape}")

# 2. Filter by mitochondrial content (if gene names contain MT-)
if any(adata.var_names.str.startswith('MT-')):
    print("Calculating mitochondrial gene fraction...")
    adata.var['mt'] = adata.var_names.str.startswith('MT-')
    sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)
    
    mt_threshold = 20  # Filter cells with >20% mitochondrial reads
    print(f"Filtering spots with >{mt_threshold}% mitochondrial content...")
    adata = adata[adata.obs['pct_mt'] < mt_threshold]
    
    # Plot QC metrics
    fig, axs = plt.subplots(1, 2, figsize=(12, 4))
    sc.pl.violin(adata, 'n_genes_by_counts', ax=axs[0], show=False)
    sc.pl.violin(adata, 'pct_mt', ax=axs[1], show=False)
    plt.tight_layout()
    plt.savefig("qc_metrics.png", dpi=300)
    plt.close()

print(f"Data shape after QC filtering: {adata.shape}")

# 3. Normalization
print("Normalizing data...")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 4. Feature selection
n_top_genes = 2000
print(f"Selecting {n_top_genes} highly variable genes...")
sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)

# Plot highly variable genes
plt.figure(figsize=(8, 6))
sc.pl.highly_variable_genes(adata, show=False)
plt.savefig("highly_variable_genes.png", dpi=300)
plt.close()

# Keep only highly variable genes for downstream analysis
# Store raw counts first
adata.raw = adata
adata = adata[:, adata.var.highly_variable]
print(f"Data shape after selecting highly variable genes: {adata.shape}")

# 5. Dimensionality reduction
print("Running PCA...")
sc.pp.pca(adata)
sc.pl.pca_variance_ratio(adata, n_pcs=30, show=False)
plt.savefig("pca_variance_ratio.png", dpi=300)
plt.close()

# 6. Compute neighborhood graph
print("Computing neighborhood graph...")
sc.pp.neighbors(adata, n_neighbors=15)

# 7. Calculate spatial neighborhood graph
print("Computing spatial neighborhood graph...")
sq.gr.spatial_neighbors(adata, coord_type="generic")

print("Preprocessing complete. Data ready for downstream analysis.")
"""

# 8. Cell Type Annotation
CELL_TYPE_ANNOTATION_TEMPLATE = """
# Cell Type Annotation Based on Marker Genes
import scanpy as sc
import squidpy as sq
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Load data (if needed)
# adata = sq.datasets.visium_hne_adata()
# OR: adata = sc.read_h5ad('your_data.h5ad')

# Make sure we have clusters
if 'leiden' not in adata.obs:
    print("Clustering data first...")
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata, resolution=0.5)

# Dictionary of known cell type markers
# Adjust based on your tissue/organ system
cell_type_markers = {
    'T cells': ['CD3D', 'CD3E', 'CD8A', 'CD4'],
    'B cells': ['CD79A', 'CD79B', 'MS4A1'],
    'Myeloid cells': ['LYZ', 'CD68', 'CD14', 'FCGR3A'],
    'Endothelial cells': ['PECAM1', 'VWF', 'CDH5'],
    'Fibroblasts': ['COL1A1', 'DCN', 'LUM'],
    # Add more cell types as needed
}

# Function to score clusters based on marker genes
def annotate_clusters(adata, cluster_key, markers_dict):
    annotations = {}
    
    for cluster in adata.obs[cluster_key].unique():
        scores = {}
        
        for cell_type, markers in markers_dict.items():
            # Filter markers present in the dataset
            valid_markers = [m for m in markers if m in adata.var_names]
            
            if not valid_markers:
                scores[cell_type] = 0
                continue
                
            # Calculate average expression in cluster vs. overall
            cluster_cells = adata[adata.obs[cluster_key] == cluster].obs_names
            cluster_expr = adata[cluster_cells, valid_markers].X
            
            if isinstance(cluster_expr, np.ndarray):
                mean_expr = np.mean(cluster_expr)
            else:  # Sparse matrix
                mean_expr = cluster_expr.mean()
                
            scores[cell_type] = float(mean_expr)
        
        # Assign the cell type with highest score
        if scores:
            best_match = max(scores.items(), key=lambda x: x[1])
            
            # Only assign if score is meaningful
            if best_match[1] > 0.1:
                annotations[cluster] = best_match[0]
            else:
                annotations[cluster] = f"Unknown-{cluster}"
    
    return annotations

# Annotate clusters
print("Annotating cell types based on marker genes...")
annotations = annotate_clusters(adata, 'leiden', cell_type_markers)

# Add annotations to adata
adata.obs['cell_type'] = adata.obs['leiden'].map(annotations)

# Print annotations
for cluster, cell_type in annotations.items():
    print(f"Cluster {cluster}: {cell_type}")

# Visualize cell types spatially
fig, ax = plt.subplots(figsize=(10, 8))
sc.pl.spatial(adata, color='cell_type', ax=ax, show=False)
plt.tight_layout()
plt.savefig("cell_type_annotation.png", dpi=300)
plt.close()

print("Cell type annotation complete. Results saved to 'cell_type_annotation.png'")
"""

# Dictionary mapping tasks to templates
TEMPLATE_DICT = {
    "spatially_variable_genes": SVG_ANALYSIS_TEMPLATE,
    "spatial_genes": SVG_ANALYSIS_TEMPLATE,
    "cluster": CLUSTERING_TEMPLATE,
    "clustering": CLUSTERING_TEMPLATE,
    "cell_type": CELL_TYPE_ANNOTATION_TEMPLATE,
    "ligand_receptor": LIGREC_TEMPLATE,
    "communication": LIGREC_TEMPLATE,
    "gene_expression": GENE_EXPRESSION_TEMPLATE,
    "visualize_gene": GENE_EXPRESSION_TEMPLATE,
    "spatial_domain": SPATIAL_DOMAIN_TEMPLATE,
    "region": SPATIAL_DOMAIN_TEMPLATE,
    "preprocessing": PREPROCESSING_TEMPLATE,
    "preprocess": PREPROCESSING_TEMPLATE,
    "comprehensive": COMPREHENSIVE_ANALYSIS_TEMPLATE,
    "pipeline": COMPREHENSIVE_ANALYSIS_TEMPLATE,
    "all": COMPREHENSIVE_ANALYSIS_TEMPLATE,
    "annotation": CELL_TYPE_ANNOTATION_TEMPLATE,
    "annotate": CELL_TYPE_ANNOTATION_TEMPLATE,
}


def get_code_template(task_description: str) -> str:
    """Get the most relevant code template for a given task description.

    Parameters:
    -----------
    task_description : str
        Description of the analysis task

    Returns:
    --------
    str
        Code template for the task
    """
    task_lower = task_description.lower()

    # Check for direct keyword matches
    for keyword, template in TEMPLATE_DICT.items():
        if keyword in task_lower:
            return template

    # Default to comprehensive template if no match
    return COMPREHENSIVE_ANALYSIS_TEMPLATE
