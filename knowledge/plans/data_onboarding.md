---
name: data_onboarding
status: enabled
description: >
  Inspect, safely acquire when explicitly requested, convert, and validate a
  spatial-transcriptomics input that is not already an analysis-ready H5AD.
---

## Inputs

- A source in `project/uploads/`, `project/outputs/`, `library/datasets/`, or
  `library/files/`
- Optional expected dimensions and required spatial coordinates

## Outputs

- `project/outputs/<name>.h5ad`
- `project/outputs/<name>.conversion.json` and download provenance when applicable

## Step Sketch

Inspect and reuse verified local inputs → download/extract only explicitly requested missing
files → convert with a deterministic tool or Coding Agent → validate the H5AD

## Details

- **Onboarding step, agent `data_onboarding_agent`:**
  - Call `inspect_spatial_data_tool` before conversion.
  - Use `download_spatial_data_tool` and `extract_spatial_archive_tool` only when local,
    checksum-verified inputs cannot be reused and acquisition was explicitly requested.
  - Call `convert_spatial_data_tool` for supported CSV layouts, Seurat RDS/H5Seurat, and other
    supported formats.
  - If inspection or conversion reports an unsupported format, stop with the format evidence so
    the plan can dispatch `coding_agent` to create and run a converter. Do not disguise the source
    as a supported format.
  - Call `validate_spatial_data_tool` on every produced H5AD, including Coding Agent outputs, and
    require spatial coordinates when the downstream method needs them.
- Report the detected format, dimensions, spatial-coordinate keys, source files, checksum,
  warnings, provenance path, and validated output path.
- Never write to the repository root or library. Relative outputs resolve only beneath
  `project/outputs/`.

## Evaluation Criteria

- The converted H5AD is non-empty, has unique observation and feature identifiers, satisfies
  declared dimension/coordinate requirements, and preserves source metadata.
- Conversion provenance names the original format, source files, warnings, checksum, and
  `project/outputs/...` artifact path.
