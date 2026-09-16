# Sample_X Affymetrix normalization and annotation QC

## Normalization

- Platform: Affymetrix Mouse Genome 430 2.0 (GPL1261).
- Input file: `library/datasets/sample_X.CEL.gz` (decompressed to `project/outputs/intermediate/sample_X.CEL`).
- Normalization method: MAS5 single-array normalization (Affymetrix MAS 5.0 algorithm) implemented via the R `affy` package.
- Post-processing: log2 transformation of MAS5 expression values.

## Annotation

- Probeset-to-gene mapping: Bioconductor `mouse4302.db` annotation package (Mouse Genome 430 2.0).
- Key type: `PROBEID` (Affymetrix probeset IDs).
- Gene identifier: current Mus musculus gene symbols (`SYMBOL`).
- Additional fields exported: `GENENAME` (gene description) and `ENTREZID` (Entrez Gene ID).
- Controls: Affymetrix control probes and records with missing/empty gene symbols were removed prior to gene-level summarization.
- Many-to-one mapping: when multiple probesets mapped to the same gene symbol, they were collapsed by **median** of log2 expression values.

## Output summaries

- Genes with normalized expression values: **22006**.
- Expression (log2 MAS5) median across genes: **7.116**.
- Expression value range (across genes):

  | Stat | Value |
  |------|-------|
  | count | 22006.000 |
  | mean | 7.177 |
  | std | 2.538 |
  | min | 0.063 |
  | 25% | 5.485 |
  | 50% | 7.116 |
  | 75% | 8.792 |
  | max | 16.400 |

## Caveats and notes

- RMA is generally preferred for multi-array analyses; MAS5 is used here as a single-array method due to environment constraints on multi-threaded RMA preprocessing.
- Expression values are on a log2 scale of MAS5 signal intensities and are not directly comparable to RMA log2 expression without appropriate downstream modeling.
- Gene symbols and Entrez IDs come from the installed `mouse4302.db` version; minor differences may exist relative to the very latest public annotation snapshots.
- This QC report was generated in Python by summarizing the exported per-gene expression table; more detailed probe-level QC (e.g., NUSE/RLE) was not computed for this single-array workflow.