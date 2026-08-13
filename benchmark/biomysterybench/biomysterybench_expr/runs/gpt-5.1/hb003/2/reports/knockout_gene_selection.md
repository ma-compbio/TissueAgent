# Knockout Gene Selection

## Chosen gene

**Final knockout-like gene:** `100126348`

## Evidence for knockout-like pattern

Using the ranked knockout_candidate_genes_ranked.tsv file (Group1 = experimental/KO, Group2 = control), the following statistics were observed for the selected gene:

- **Group1 (KO) expression:**
  - mean_Group1 = 0.000
  - median_Group1 = 0.000
  - detection_Group1 = 0.000 (fraction of samples with expression)
- **Group2 (control) expression:**
  - mean_Group2 = 6.401
  - median_Group2 = 6.845
  - detection_Group2 = 1.000
- **Differential statistics (Group1 vs Group2):**
  - log2FC_Group1_vs_Group2 = -12.644 (strongly negative, indicating loss in Group1)
  - knockout_score = 34615.5
  - stringency = relaxed
  - stringent_hit = True

These values show an essentially complete loss of expression in the KO group (zero mean and detection), combined with robust, ubiquitous expression in controls (highest mean and full detection), and the most extreme negative log2 fold-change among the candidate genes.

## Comparison with other top candidates

- `100616396`: 
  - Group1: mean_Group1 = 0.000, detection_Group1 = 0.000
  - Group2: mean_Group2 = 3.794, detection_Group2 = 0.667
  - log2FC_Group1_vs_Group2 = -11.890
  - knockout_score = 47174.0, stringency = relaxed, stringent_hit = False
- `100616150`: 
  - Group1: mean_Group1 = 0.000, detection_Group1 = 0.000
  - Group2: mean_Group2 = 3.246, detection_Group2 = 0.667
  - log2FC_Group1_vs_Group2 = -11.665
  - knockout_score = 47602.5, stringency = relaxed, stringent_hit = False

All three candidates show complete loss of expression in Group1 and strong down-regulation versus Group2. However, the chosen gene has: (i) the highest mean and median expression and full detection in Group2, (ii) the most negative log2 fold-change, (iii) the lowest knockout_score, and (iv) is the only one marked as a stringent_hit. Together, these features make it the clearest and most unique knockout-like signature among the ranked candidates.