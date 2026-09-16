"""LangChain tool definitions for safe spatial-data onboarding."""

from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.data_onboarding_agent.tools_impl.onboarding import (
    convert_spatial_data,
    download_spatial_data,
    extract_spatial_archive,
    inspect_spatial_data,
    validate_spatial_data,
)


DataOnboardingTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=download_spatial_data,
        name="download_spatial_data_tool",
        description=(
            "Safely downloads one explicitly requested HTTPS file into project/outputs. "
            "Validates redirects and resolved addresses, streams through a partial file, "
            "enforces size limits, verifies a publisher checksum when supplied, and records "
            "SHA-256 provenance."
        ),
    ),
    StructuredTool.from_function(
        func=extract_spatial_archive,
        name="extract_spatial_archive_tool",
        description=(
            "Safely extracts one ZIP, TAR, TAR.GZ, TGZ, or single GZIP archive. "
            "Rejects path traversal, links, executable content, excessive entries, and excessive "
            "expansion."
        ),
    ),
    StructuredTool.from_function(
        func=inspect_spatial_data,
        name="inspect_spatial_data_tool",
        description=(
            "Inspects a local spatial-transcriptomics file or directory, detects its format, "
            "and reports required/missing companion files without modifying it."
        ),
    ),
    StructuredTool.from_function(
        func=convert_spatial_data,
        name="convert_spatial_data_tool",
        description=(
            "Converts a supported local spatial-transcriptomics source to H5AD under "
            "project/outputs while preserving source metadata. "
            "Supports H5AD, Loom, Seurat RDS/H5Seurat, 10x MEX/H5, delimited matrices, "
            "CosMx, MERSCOPE, Visium, Visium HD, Xenium, and compatible Stereo-seq. "
            "Unsupported formats return a visible error for Coding Agent escalation. "
            "Conversion never installs dependencies."
        ),
    ),
    StructuredTool.from_function(
        func=validate_spatial_data,
        name="validate_spatial_data_tool",
        description=(
            "Validates an H5AD's shape, unique identifiers, metadata, spatial coordinates, "
            "and expected dimensions."
        ),
    ),
]
