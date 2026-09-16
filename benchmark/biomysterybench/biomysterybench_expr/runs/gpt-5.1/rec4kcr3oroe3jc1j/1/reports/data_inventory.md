# Data inventory and time-axis definition

## 1. Data inventory

**Directory scanned:** `library/datasets/`

**Files found:**

1. `RHYTHMIC.txt`
   - Format: comma-separated text with quoted column names.
   - Loaded as a 100 × 13 table.
   - Columns:
     - `GENE`: character, 100 unique gene identifiers (e.g., `GENE32`, `GENE15`, ...).
     - `ZT0`, `ZT4`, `ZT8`, `ZT12`, `ZT16`, `ZT20`, `ZT24`, `ZT28`, `ZT32`, `ZT36`, `ZT40`, `ZT44`.
   - The 12 `ZT*` columns are numeric (float64) and represent expression values.
   - Interpretation: a normalized RNA-seq (or microarray-like) gene-by-sample expression matrix with:
     - 100 genes (rows).
     - 12 samples (columns) corresponding to Zeitgeber Times from ZT0 to ZT44 in 4-hour increments.

No additional files (e.g., separate sample metadata or alternative matrices) were found under `library/datasets/`, so `RHYTHMIC.txt` is taken as the **primary and only** expression matrix.

## 2. Primary time-ordered expression matrix

- **Primary matrix file used:** `library/datasets/RHYTHMIC.txt`.
- **Dimensions after processing:** 100 genes × 12 samples.
- **Orientation:**
  - Rows = genes, indexed by the `GENE` column.
  - Columns = samples/timepoints, named `ZT0`, `ZT4`, ..., `ZT44`.
- **Time ordering of samples:**
  - Sample column names follow the pattern `ZT<number>` (Zeitgeber Time in hours).
  - Parsed numeric times: `ZT0` → 0, `ZT4` → 4, ..., `ZT44` → 44.
  - Columns were ordered by increasing numeric time: `ZT0`, `ZT4`, `ZT8`, `ZT12`, `ZT16`, `ZT20`, `ZT24`, `ZT28`, `ZT32`, `ZT36`, `ZT40`, `ZT44`.

The final time-ordered expression matrix was saved as a tab-delimited file with genes as rows and samples as columns at:

- `project/outputs/tables/expression_matrix_time_ordered.tsv`

## 3. Timepoints file

- For each sample/column, the Zeitgeber Time in hours was extracted from the column name.
- The resulting mapping is:

| sample_id | time (hours) |
|-----------|--------------|
| ZT0       | 0            |
| ZT4       | 4            |
| ZT8       | 8            |
| ZT12      | 12           |
| ZT16      | 16           |
| ZT20      | 20           |
| ZT24      | 24           |
| ZT28      | 28           |
| ZT32      | 32           |
| ZT36      | 36           |
| ZT40      | 40           |
| ZT44      | 44           |

These timepoints were written to:

- `project/outputs/tables/timepoints_assigned.tsv`

with columns:

- `sample_id`: matches the column names in the expression matrix.
- `time`: numeric time in hours.

Since explicit times are encoded in the column names, **no assumptions** about spacing were required; the series is regularly spaced at 4-hour intervals from 0 h to 44 h.

## 4. Caveats and potential ambiguities

- **Normalization details unknown:**
  - The file appears to contain normalized expression values (centered and scaled log-expression or similar), but the exact normalization pipeline (e.g., TPM, FPKM, log2 CPM with voom, z-scores) is not documented in the file.
  - Downstream rhythmicity analysis should assume relative expression and may need robustness checks if absolute scaling matters.

- **Biological/technical replication not represented:**
  - Only a single value per gene per timepoint is present; no explicit biological or technical replicates are encoded.
  - This limits the ability to estimate within-timepoint variance; methods assuming replicates should be applied cautiously.

- **Experimental context missing:**
  - The species, tissue, sequencing platform, and experimental conditions are not specified in the dataset.
  - This does not block rhythmicity analysis on this matrix but may limit biological interpretation.

- **No separate metadata file:**
  - All time-related information is inferred solely from column names; there is no external sample metadata to cross-check.
  - If additional metadata exist outside the provided workspace, they should be integrated in future steps for more detailed analyses.
