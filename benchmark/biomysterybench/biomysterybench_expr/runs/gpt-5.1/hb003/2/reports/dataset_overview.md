# Dataset overview

This report summarizes expression/count datasets found under `library/datasets/` and describes their structure and inferred properties.

## Dataset: `library/datasets/norm_counts_TPM.tsv`

- **Format:** tsv
- **Orientation:** genes_in_rows (genes in rows, samples in columns; first column is gene identifiers, remaining columns are sample identifiers)
- **Number of genes (rows):** 39376
- **Number of samples (columns):** 5
- **Gene identifier type (inferred):** NCBI_GeneID_numeric (assumed)
- **Sample identifier type (inferred):** condition_replicate_label (assumed)
- **Sparsity (fraction of zero entries):** 0.4298
- **Per-sample library sizes:** min=1000002.80, median=1000003.50, max=1000012.87
- **Per-gene detection rate (fraction of samples with nonzero expression):** min=0.00, median=0.80, max=1.00

**Notes and assumptions:** Values interpreted as normalized_counts_or_expression based on filename and numeric type. Assumed first column 'GeneID' contains gene IDs and remaining 5 columns are samples.

## Dataset: `library/datasets/raw_counts.tsv`

- **Format:** tsv
- **Orientation:** genes_in_rows (genes in rows, samples in columns; first column is gene identifiers, remaining columns are sample identifiers)
- **Number of genes (rows):** 39376
- **Number of samples (columns):** 5
- **Gene identifier type (inferred):** NCBI_GeneID_numeric (assumed)
- **Sample identifier type (inferred):** sample_label (assumed)
- **Sparsity (fraction of zero entries):** 0.4298
- **Per-sample library sizes:** min=20062235.00, median=21729535.00, max=25523288.00
- **Per-gene detection rate (fraction of samples with nonzero expression):** min=0.00, median=0.80, max=1.00

**Notes and assumptions:** Values interpreted as raw_counts based on filename and numeric type. Assumed first column 'GeneID' contains gene IDs and remaining 5 columns are samples.

---

## Global assumptions and caveats

- Only files with tabular structure and predominantly numeric entries beyond the first column were treated as expression/count matrices.
- For such matrices, genes were assumed to be in rows and samples in columns, with the first column containing gene identifiers and the remaining columns containing sample identifiers.
- Gene identifiers that are almost entirely numeric were interpreted as NCBI GeneIDs. No external annotation resources beyond the provided `gene_info.gz` header inspection were used.
- Sample identifiers were inferred from column naming patterns (e.g., `Control_1`, `KO_1`) and treated as condition/replicate labels or generic sample labels.
- Sparsity was defined as the fraction of entries equal to zero in the numeric portion of each matrix.
- Per-sample library sizes were computed as the sum of all numeric values per sample column. For normalized TPM-like data, these library sizes are expected to be approximately constant across samples.
- Per-gene detection rate was defined as the fraction of samples with value strictly greater than zero.
- No attempt was made to distinguish technical zeros from biological zeros; all zero entries were treated uniformly.