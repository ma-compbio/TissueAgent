from langchain.tools import StructuredTool
from typing import Dict, Any
from agents.agent_registry.data_analysis_agent.tools_impl.code_templates import get_code_template

def generate_spatial_analysis_code(task_description: str, use_existing_tools: bool = True, execute_code: bool = True) -> Dict[str, Any]:
    """
    Enhanced code generation with prioritized built-in visualization
    """
    task_lower = task_description.lower()
    
    # High-priority clustering and visualization tools
    if "cluster" in task_lower:
        # Directly use the spatial_clustering_tool
        from src.tools.data_analysis_tools import spatial_clustering_tool
        
        # Call the tool to create visualization
        result = spatial_clustering_tool.run({})
        
        return {
            "task": task_description,
            "visualization": "spatial_clustering.png",
            "method": "Built-in Spatial Clustering Tool",
            "message": "Spatial clustering visualization created directly using built-in tool."
        }
    
    # Get the most relevant code template for the task
    code_template = get_code_template(task_description)
    
    # Generate explanation based on the task
    explanation = "This code:"
    
    if "spatially variable" in task_lower or "spatial gene" in task_lower:
        explanation += "\n- Identifies genes with spatial patterns using Moran's I spatial autocorrelation"
        explanation += "\n- Visualizes the expression of top spatially variable genes"
        explanation += "\n- Returns a list of genes with significant spatial patterns"
        
    elif "cluster" in task_lower:
        explanation += "\n- Performs clustering using the Leiden algorithm"
        explanation += "\n- Visualizes the clusters on the spatial coordinates"
        explanation += "\n- Identifies marker genes for each cluster"
        explanation += "\n- Helps identify different cell populations in the tissue"
        
    elif "ligand" in task_lower or "receptor" in task_lower or "communication" in task_lower:
        explanation += "\n- Analyzes potential cell-cell communication via ligand-receptor interactions"
        explanation += "\n- Identifies significant interactions between different clusters"
        explanation += "\n- Visualizes the interaction network"
        explanation += "\n- Helps understand how different cell types communicate in the tissue"
        
    elif any(x in task_lower for x in ["gene expression", "visualize gene"]):
        explanation += "\n- Visualizes the spatial expression pattern of specific genes"
        explanation += "\n- Creates multiple plots for different genes"
        explanation += "\n- Also shows gene expression across different clusters if available"
        explanation += "\n- Helps understand where genes are expressed in the tissue"
        
    elif any(x in task_lower for x in ["domain", "region", "area"]):
        explanation += "\n- Identifies spatial domains or regions in the tissue"
        explanation += "\n- Uses spatially variable genes to define coherent regions"
        explanation += "\n- Finds marker genes for each domain"
        explanation += "\n- Helps identify functional or anatomical regions in the tissue"
        
    elif "preprocess" in task_lower:
        explanation += "\n- Performs quality control and filtering"
        explanation += "\n- Normalizes and log-transforms the data"
        explanation += "\n- Identifies highly variable genes"
        explanation += "\n- Computes neighborhood graphs"
        explanation += "\n- Prepares the data for downstream analysis"
        
    else:
        explanation += "\n- Provides a comprehensive analysis workflow"
        explanation += "\n- Includes preprocessing, clustering, finding marker genes"
        explanation += "\n- Identifies spatially variable genes"
        explanation += "\n- Analyzes spatial relationships between cell types"
        explanation += "\n- Creates visualizations for all key results"
    
    # Execute the code if requested
    
    # Build the result dictionary
    result = {
        "task": task_description,
        "use_existing_tools": False,
        "code": code_template,
        "explanation": explanation,
        "instructions": "To use this code, make sure you have scanpy and squidpy installed. You may need to adjust parameters based on your specific dataset."
    }
    
    # Add execution results if available
    if execution_results:
        result["execution"] = execution_results
        
        if execution_results["success"]:
            result["created_files"] = execution_results["created_files"]
            file_list = ", ".join(execution_results["created_files"]) if execution_results["created_files"] else "No files created"
            result["message"] = f"Code executed successfully. Visualization files: {file_list}"
        else:
            result["message"] = f"Code execution failed: {execution_results['error']}"
    
    return result

generate_spatial_analysis_code_tool = StructuredTool.from_function(
    func=generate_spatial_analysis_code,
    name="generate_spatial_analysis_code",
    description="Generate and execute Python code for spatial transcriptomics analysis tasks."
)

if __name__ == "__main__":
    # Example usage
    result = generate_spatial_analysis_code("Find spatially variable genes and visualize them")
    print(result["explanation"])
    print("\nCode snippet preview:")
    print("\n".join(result["code"].split("\n")[:10]))
    
    if "execution" in result:
        print("\nExecution results:")
        if result["execution"]["success"]:
            print(f"Created files: {result['created_files']}")
        else:
            print(f"Execution failed: {result['execution']['error']}")
