---
name: go_enrichment_analysis
status: enabled
description: >
  Run Gene Ontology enrichment analysis (ORA or GSEA) on differential or ranked
  gene lists. Produces an enrichment results table, a dotplot figure, and a
  concise interpretation report summarizing top enriched terms.
---

## Inputs
- Foreground genes (from DE/top markers/ranked list)
- Background universe or ranked statistic (if required by method)
- Analysis configuration (GO branch, significance thresholds)

## Outputs
- tables/go_enrichment.tsv
- figures/go_enrichment_dotplot.png
- reports/go_enrichment_summary.md

## Step Sketch
Prepare foreground/background gene sets with method parameters → run GO enrichment (ORA/GSEA as appropriate) → export enrichment table + dotplot and concise interpretation report

## Evaluation Criteria
- tables/go_enrichment.tsv exists and has significant terms
- figures/go_enrichment_dotplot.png exists
- reports/go_enrichment_summary.md exists

## Defaults
- ontology: "BP"
- fdr_threshold: 0.05
- top_terms_for_plot: 20

## Checklist
- Prepare valid foreground/background inputs (or ranked list) and record config
- Run GO enrichment with explicit ontology and multiple-testing correction
- Export enrichment results table and dotplot figure artifacts
- Summarize top enriched terms, effect direction, and caveats in report
