#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("Usage: convert_seurat_to_mtx.R INPUT.(rds|h5Seurat) OUTPUT_DIR")
}

input_path <- normalizePath(args[[1]], mustWork = TRUE)
output_dir <- args[[2]]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
matrix_dir <- file.path(output_dir, "matrix")
dir.create(matrix_dir, recursive = TRUE, showWarnings = FALSE)

required <- c("Seurat", "Matrix")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop(paste("Missing required R packages:", paste(missing, collapse = ", ")))
}

if (grepl("\\.h5seurat$", input_path, ignore.case = TRUE)) {
  if (!requireNamespace("SeuratDisk", quietly = TRUE)) {
    stop("SeuratDisk is required to read H5Seurat input; it was not installed automatically.")
  }
  object <- SeuratDisk::LoadH5Seurat(input_path, verbose = FALSE)
} else {
  object <- readRDS(input_path)
}

if (!inherits(object, "Seurat")) {
  stop("Input is not a Seurat object.")
}

assay_name <- Seurat::DefaultAssay(object)
layers <- SeuratObject::Layers(object[[assay_name]])
preferred <- layers[grepl("^counts($|\\.)", layers)]
if (length(preferred) == 0) {
  preferred <- layers[grepl("^data($|\\.)", layers)]
}
if (length(preferred) == 0) {
  stop(paste("No counts or data layer found in assay", assay_name))
}
if (length(preferred) > 1) {
  object <- SeuratObject::JoinLayers(
    object,
    assay = assay_name,
    layers = preferred,
    new = "tissueagent_counts"
  )
  layer_name <- "tissueagent_counts"
} else {
  layer_name <- preferred[[1]]
}

counts <- SeuratObject::LayerData(object, assay = assay_name, layer = layer_name)
if (is.null(rownames(counts)) || is.null(colnames(counts))) {
  stop("Seurat expression layer lacks gene or cell identifiers.")
}
if (anyDuplicated(rownames(counts)) || anyDuplicated(colnames(counts))) {
  stop("Seurat expression layer has duplicate gene or cell identifiers.")
}

Matrix::writeMM(counts, file.path(matrix_dir, "matrix.mtx"))
features <- data.frame(
  gene_id = rownames(counts),
  gene_name = rownames(counts),
  check.names = FALSE
)
write.table(
  features,
  file.path(matrix_dir, "genes.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE,
  col.names = FALSE
)
write.table(
  colnames(counts),
  file.path(matrix_dir, "barcodes.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE,
  col.names = FALSE
)

metadata <- object[[]]
metadata <- metadata[colnames(counts), , drop = FALSE]
write.csv(metadata, file.path(output_dir, "metadata.csv"), quote = TRUE)

coordinates <- tryCatch(
  Seurat::GetTissueCoordinates(object),
  error = function(error) NULL
)
if (!is.null(coordinates) && ncol(coordinates) >= 2) {
  coordinates <- coordinates[colnames(counts), , drop = FALSE]
  write.csv(coordinates, file.path(output_dir, "spatial.csv"), quote = TRUE)
}

message(
  sprintf(
    "Exported %d genes x %d cells from assay '%s' layer '%s'.",
    nrow(counts),
    ncol(counts),
    assay_name,
    layer_name
  )
)
