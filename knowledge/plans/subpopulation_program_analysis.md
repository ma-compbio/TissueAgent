---
name: subpopulation_program_analysis
status: enabled
description: >
  Test whether a target cell type inside a focal group/region (e.g. a cellular
  community, spatial niche, or condition) follows a distinct molecular program
  compared with the same cell type elsewhere. Runs differential expression to
  derive marker genes, uses the Gene Agent to interpret and verify the
  biological processes those markers represent (a verified process narrative,
  NOT GO/GSEA enrichment tables), and has the Critic Agent weigh the evidence
  for/against a distinct program.
---

## Inputs
- Dataset (.h5ad or table) with a cell-type field and a grouping field
- target_cell_type: the cell type to compare (a value in the cell-type field)
- focal_group: the group/region of interest (a value in the grouping field)
- comparison_groups: one or more other groups of the same field to contrast against
- grouping_field: the .obs column defining focal vs comparison groups
  (e.g. a cellular community, spatial niche, region, or condition)

## Outputs
- tables/de_<target>_<focal>_vs_rest.tsv  (marker genes with log2FC + adjusted P)
- figures/volcano_<target>_<focal>.png
- tables/markers_<target>_<focal>_symbols.txt  (plain gene-symbol list for the Gene Agent, one symbol per line, no header)
- workspace/gene_agent/<request_id>/  (Gene Agent process narrative + verification)
- reports/criticism.json  (Critic Agent's evidence assessment)
- reports/<task_name>_report.md

## Step Sketch
Subset target cell type → DE focal vs comparison groups → marker set + volcano →
Coding Agent extracts the significant marker symbols into a plain gene-list file →
Gene Agent process interpretation/verification of that gene list → critic weighs
evidence for a distinct program → report

## Gene Agent input contract (important)
The Gene Agent is an external agent whose tool takes an inline `gene_list`
(List[str] of canonical symbols) — it does NOT read files. So the marker `.tsv`
from the DE step cannot be handed to it directly. Always insert a Coding Agent
step that reads the significant-marker table and writes the symbols to
`tables/markers_<target>_<focal>_symbols.txt` (one symbol per line, no header)
AND prints the full symbol list in its summary. The manager then forwards those
symbols inline as the Gene Agent's `gene_list`.

The Gene Agent cascade verifies every claim sequentially and is slow, so it
takes AT MOST 10 genes. The Coding Agent step must therefore rank the
significant markers (e.g. by adjusted P ascending, breaking ties by |log2FC|)
and keep only the **top 10**, written most-significant-first. Note the 10-gene
cap as a caveat in the final report.

## Evaluation Criteria
- Marker table exists with adjusted P values; significant set (adj P < 0.05) reported
- Volcano plot saved under figures/
- Plain gene-symbol list saved to tables/markers_<target>_<focal>_symbols.txt (non-empty)
- Gene Agent artifacts saved under workspace/gene_agent/<request_id>/
- Critic assessment (support vs. confounds) saved to reports/criticism.json
- Report summarizes marker set, verified processes, and the distinct-program verdict

## Defaults
- de_method: Wilcoxon rank-sum (scanpy sc.tl.rank_genes_groups), on log-normalized data
- significance: adjusted P < 0.05 (Benjamini–Hochberg)
- min_cells_per_group: 30  (flag as a caveat if any group falls below this)
- gene_set_interpretation: Gene Agent verified process narrative (NOT GO/GSEA/dotplot)
- include_caveats: true

## Checklist
- Coding Agent: Load dataset, subset to target_cell_type, define focal vs comparison groups from grouping_field, print per-group cell counts (flag small groups)
- Coding Agent: Run differential expression (focal vs comparison), keep genes at adjusted P < 0.05 as the marker set, save tables/de_<target>_<focal>_vs_rest.tsv
- Coding Agent: Produce a volcano plot of the differentially expressed genes, save to figures/volcano_<target>_<focal>.png
- Coding Agent: Extract the significant marker symbols (adjusted P < 0.05) from tables/de_<target>_<focal>_vs_rest.tsv, deduplicate and uppercase to canonical symbols, RANK by adjusted P ascending (tie-break by |log2FC| descending) and keep only the TOP 10 (most-significant-first), write them to tables/markers_<target>_<focal>_symbols.txt (one symbol per line, no header), and print the list in the summary so the manager can forward it to the Gene Agent
- Gene Agent: Given the prepared top-10 marker gene list (canonical symbols from tables/markers_<target>_<focal>_symbols.txt, passed inline as gene_list), propose + verify the biological processes it represents — a verified process narrative, not an enrichment table
- Critic Agent: Weigh DE + verified-process evidence for/against a distinct molecular program; note confounds, low power, and alternative explanations, save to reports/criticism.json
- Reporter Agent: Summarize the marker set, verified biological processes, the distinct-program verdict, and caveats
