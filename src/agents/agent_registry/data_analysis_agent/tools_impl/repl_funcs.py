from dataclasses import dataclass

from agents.agent_registry.data_analysis_agent.tools_impl.repl_spatial_clustering_funcs_impl import *
from agents.agent_registry.data_analysis_agent.tools_impl.repl_ligand_receptor_funcs_impl import *

@dataclass
class REPLFunc:
    name: str
    description: str
    code: str

REPLFuncs = {
    "Spatial Clustering analysis": [
        REPLFunc(
            name="preprocess_adata",
            description=PreprocessAnndataDescription,
            code=PreprocessAnndataCode,
        ),
        REPLFunc(
            name="find_marker_genes",
            description=FindMarkerGenesDescription,
            code=FindMarkerGenesCode,
        ),
        REPLFunc(
            name="plot_gene_heatmap",
            description=PlotGeneHeatmapDescription,
            code=PlotGeneHeatmapCode,
        ),
        REPLFunc(
            name="query_gene_expression",
            code=QueryGeneExpressionCode,
            description=QueryGeneExpressionDescription,
        ),
        REPLFunc(
            name="spatial_clustering",
            code=SpatialClusteringCode,
            description=SpatialClusteringDescription,
        ),
        # REPLFunc(
        #     name="spatial_coexpression",
        #     code=SpatialCoexpressionCode,
        #     description=SpatialCoexpressionDescription,
        # ),
    ],
    "Ligand-Receptor analysis": [
        REPLFunc(
            name="find_ligand_receptor_interactions",
            code=FindLigandReceptorInteractionsCode,
            description=FindLigandReceptorInteractionsDescription,
        ),
        REPLFunc(
            name="plot_ligand_receptor_interactions",
            code=PlotLigandReceptorInteractionsCode,
            description=PlotLigandReceptorInteractionsDescription,
        ),
        REPLFunc(
            name="plot_ligand_receptor_heatmap",
            code=PlotLigandReceptorHeatmapCode,
            description=PlotLigandReceptorHeatmapDescription,
        ),
        REPLFunc(
            name="query_interaction_at_coordinates",
            code=QueryInteractionAtCoordinatesCode,
            description=QueryInteractionAtCoordinatesDescription,
        ),
        REPLFunc(
            name="plot_interaction_network",
            code=PlotInteractionNetworkCode,
            description=PlotInteractionNetworkDescription,
        ),
    ],
}

FormattedREPLFuncNames = "\n".join(
    f"      * {section}\n" + "\n".join(f"        - {fn.name}" for fn in funcs)
    for section, funcs in REPLFuncs.items()
)
