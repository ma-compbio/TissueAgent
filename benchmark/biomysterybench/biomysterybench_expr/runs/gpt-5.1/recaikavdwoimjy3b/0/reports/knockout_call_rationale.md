# Final knockout gene call

**Selected knockout gene:** `ENSG00000178498.15`

## Evidence from KO-pattern metrics

From `project/outputs/tables/ko_candidate_genes_ranked.tsv`:

- `ENSG00000178498.15` is one of only two rows with `is_KO_candidate == True`.
- It has the highest `composite_score` among all genes:
  - `composite_score = 0.805851`, higher than the next-best gene (`ENSG00000086289.11`, 0.778181) and the other flagged KO candidate `ENSG00000152804.10` (0.763127).
- Expression means:
  - `mean_KO = 0.0`
  - `mean_control ≈ 3.823`
  - This indicates a complete loss of normalized expression in KO samples versus robust expression in controls.
- Per-sample normalized expression pattern (columns `sample_rnaseq1–6`):
  - KO samples (1–3): `0.0, 0.0, 0.0`
  - Control samples (4–6): approximately `4.13, 3.91, 3.43`
  - This is an ideal knockout signature: essentially off in every KO replicate and consistently on in every control replicate.

The other flagged KO candidate, `ENSG00000152804.10`, also shows a clean on/off pattern (0 in all KO samples, ~3.2–3.5 in controls) but with slightly lower `mean_control` and a lower composite score.

## Evidence from differential expression results

From `project/outputs/tables/de_results_ko_vs_ctrl.tsv` for `ENSG00000178498.15`:

- `log2FoldChange ≈ -7.99`
- `padj ≈ 2.78e-04`

This represents an extremely strong and statistically significant down‑regulation in KO vs control.
Among top-scoring genes in the KO candidate table, `ENSG00000178498.15` has one of the largest negative log2 fold-changes and a robust adjusted p-value, consistent with a true targeted knockout.

`ENSG00000152804.10` also has a strong DE signal:

- `log2FoldChange ≈ -7.19`
- `padj ≈ 1.34e-03`

However, its adjusted p-value is less extreme, and its composite score is lower than that of `ENSG00000178498.15`.

## Comparison to other high-scoring candidates

Among the top genes by `composite_score`, several non-flagged genes (e.g. `ENSG00000086289.11`, `ENSG00000196653.11`, `ENSG00000118508.4`, `ENSG00000183837.9`) show strong down‑regulation but do **not** exhibit the same perfectly clean KO-vs-control separation:

- Their `mean_KO` values are > 0, reflecting residual expression in KO samples.
- Some show non-zero expression in one or more KO replicates.
- Many have similar or even stronger statistical significance (`padj`), but the per-sample pattern is more compatible with secondary effects or partial down‑regulation, rather than a direct, fully penetrant knockout.

By contrast, `ENSG00000178498.15` combines:

- The highest composite KO-pattern score.
- Complete absence of expression in all three KO samples.
- Strong and consistent expression in all three controls.
- A very large negative log2 fold-change with a significant adjusted p-value.

This combination is uniquely clean among all candidates, making it the most plausible primary knockout target.

## Co-targeting considerations

The second flagged candidate, `ENSG00000152804.10`, shows:

- `mean_KO = 0.0`, `mean_control ≈ 3.33`.
- KO per-sample expression: `0.0, 0.0, 0.0`.
- Control per-sample expression: ~`3.24–3.50`.
- `log2FoldChange ≈ -7.19`, `padj ≈ 1.34e-03`.
- `composite_score = 0.763127`.

Thus it also has an on/off-like pattern and a strong DE signal, compatible with a possible co‑target or tightly linked effect. However:

- Its composite score and control mean are both modestly lower than those of `ENSG00000178498.15`.
- Several non-flagged genes show strong but not absolute down‑regulation, suggesting broader downstream expression changes rather than multiple equally direct targets.

Given the stronger KO-pattern metrics and DE statistics for `ENSG00000178498.15`, and the lack of any other gene with an equally strong and clearly indistinguishable pattern, the most parsimonious interpretation is that `ENSG00000178498.15` is the primary, intended knockout gene. `ENSG00000152804.10` may be affected (e.g. through regulatory or pathway-level consequences), but the evidence is weaker for it being a direct co‑target.

## Gene symbol mapping

The available tables (`ko_candidate_genes_ranked.tsv`, `de_results_ko_vs_ctrl.tsv`, and `normalized_expression.tsv`) only provide Ensembl-style gene identifiers in the `GeneID` field. No explicit gene symbol or annotation column is present in these files or in the provided library resources, so a reliable symbol mapping cannot be inferred within this workspace.

Accordingly, the final knockout call is reported using the `GeneID` as provided: `ENSG00000178498.15`.
