from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from agents.agent_utils import file_retriever_tool

# ╔═══════════════════════╗
# ║ 🤐 Unzip Tool         ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.extract_tool as extract


class ExtractToolInput(BaseModel):
    filepath: str = Field(description="path to zip/tar archive")


extract_tool = StructuredTool.from_function(
    func=extract.extract_file,
    name="extract_tool",
    description="Extracts a ZIP or TAR archive.",
    args_schema=ExtractToolInput,
)


# ╔═══════════════════════╗
# ║ 🚀 CosMx              ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.cosmx_reader_tool as cosmx

cosmx_description = " ".join(
    """Converts CosMx data to an AnnData format,
saved as a .h5ad file. REQUIRES FILES "*exprMat_file.csv" and "*metadat_file.csv"
TO EXIST. Note that the star represents any string.
""".splitlines()
)


class CosmxReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with cosmx files")


cosmx_reader_tool = StructuredTool.from_function(
    func=cosmx.convert_to_h5ad,
    name="cosmx_reader_tool",
    description=cosmx_description,
    args_schema=CosmxReaderInput,
)


# ╔═══════════════════════╗
# ║ 🧜 MERSCOPE           ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.merscope_reader_tool as merscope

merscope_description = " ".join(
    """Converts MERSCOPE data to an AnnData format,
saved as a .h5ad file. REQUIRES FILES "cell_by_gene.csv", "cell_metadata.csv" 
TO EXIST.""".splitlines()
)


class MerscopeReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with merscope files")


merscope_reader_tool = StructuredTool.from_function(
    func=merscope.convert_to_h5ad,
    name="merscope_reader_tool",
    description=merscope_description,
    args_schema=MerscopeReaderInput,
)


# ╔═══════════════════════╗
# ║ 📻 Stereo-seq         ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.stereoseq_reader_tool as stereoseq

stereoseq_description = " ".join(
    """Converts Stereo-seq data to an AnnData format,
saved as a .h5ad file. REQUIRES A SINGLE "*.h5ad" TO EXIST""".splitlines()
)


class StereoseqReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with stereoseq files")


stereoseq_reader_tool = StructuredTool.from_function(
    func=stereoseq.convert_to_h5ad,
    name="stereoseq_reader_tool",
    description=stereoseq_description,
    args_schema=StereoseqReaderInput,
)


# ╔═══════════════════════╗
# ║ 🔬 Visium             ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.visium_reader_tool as visium

visium_description = " ".join(
    """Converts Visium HD data to an AnnData format,
saved as a .h5ad file. REQUIRES FILE "*filtered_feature_bc_matrix.h5". REQUIRES 
"scalefactors_json.json", "tissue_positions.csv", "tissue_hires_image.png", and 
"tissue_lowres_image.png" TO BE IN A SEPERATE DIRECTORY CALLED "spatial/".""".splitlines()
)


class VisiumReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with visium files")


visium_reader_tool = StructuredTool.from_function(
    func=visium.convert_to_h5ad,
    name="visium_reader_tool",
    description=visium_description,
    args_schema=VisiumReaderInput,
)

# ╔═══════════════════════╗
# ║ 🔬 Visium HD          ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.visiumhd_reader_tool as visiumhd

visiumhd_description = " ".join(
    """Converts Visium data to an AnnData format,
saved as a .h5ad file. REQUIRES A "*feature_slice.h5" file and "spatial/",
"binned_outputs/" DIRECTORIES.""".splitlines()
)


class VisiumHDReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with visium hd files")


visiumhd_reader_tool = StructuredTool.from_function(
    func=visiumhd.convert_to_h5ad,
    name="visiumhd_reader_tool",
    description=visiumhd_description,
    args_schema=VisiumHDReaderInput,
)

# ╔═══════════════════════╗
# ║ ✨ Xenium             ║
# ╚═══════════════════════╝

import agents.agent_registry.data_processing_agent.tools_impl.xenium_reader_tool as xenium

xenium_description = " ".join(
    """Converts Xenium data to an AnnData format,
saved as a .h5ad file. REQUIRES FILES "cell_feature_matrix.h5", "cells.parquet"
TO EXIST.""".splitlines()
)


class XeniumReaderInput(BaseModel):
    dataset_dir: str = Field(description="path to directory with xenium files")


xenium_reader_tool = StructuredTool.from_function(
    func=xenium.convert_to_h5ad,
    name="xenium_reader_tool",
    description=xenium_description,
    args_schema=XeniumReaderInput,
)

DataProcessingTools = [
    file_retriever_tool,
    extract_tool,
    cosmx_reader_tool,
    merscope_reader_tool,
    stereoseq_reader_tool,
    visium_reader_tool,
    visiumhd_reader_tool,
    xenium_reader_tool,
]
