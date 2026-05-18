# Exploration Log

OBSERVATION 1:
The dataset contains 228635 cells and 238 genes. The selected label column is 'leiden' with 32 distinct labels; the most abundant label has 19947 cells and the 10 most frequent labels together account for 142510 cells. Spatial coordinates are available; when present, the coordinate matrix has shape (228635, 2) with example entries [[-8360.2421875, -264.4503479003906], [-8315.4345703125, -251.4062042236328], [-8339.861328125, -256.9504089355469]]. The observation and feature metadata include 7 obs columns and 0 var columns, with OBS columns ['Sample_ID', 'Batch', 'UMI Count', 'leiden', 'Complexity', 'Populations', 'Purity'] (first 8 shown).

OBSERVATION 2:
Using k=15 spatial nearest neighbors on 228635 cells, we computed same-label neighbor fractions for all 32 'leiden' clusters. Global cluster abundances ranged from 995 to 19947 cells per label (0.0044 to 0.0872 of all cells). The top 5 clusters by same-label concentration score (same_label_fraction / global_abundance) were: 
- Label 28 (code=26) with 2027 cells (0.0089 of all cells) had same-label neighbors for 0.720 of its k-nearest neighbors and a concentration score of 81.22.
- Label 15 (code=15) with 1562 cells (0.0068 of all cells) had same-label neighbors for 0.533 of its k-nearest neighbors and a concentration score of 78.05.
- Label 20 (code=20) with 3131 cells (0.0137 of all cells) had same-label neighbors for 0.853 of its k-nearest neighbors and a concentration score of 62.26.
- Label 29 (code=27) with 2292 cells (0.0100 of all cells) had same-label neighbors for 0.617 of its k-nearest neighbors and a concentration score of 61.56.
- Label 31 (code=29) with 1542 cells (0.0067 of all cells) had same-label neighbors for 0.410 of its k-nearest neighbors and a concentration score of 60.76.
For each of these rare-but-tight clusters, we identified the top 3 non-self neighboring clusters by enrichment over global abundance among their spatial neighbors (requiring at least 20 neighbor contacts per partner label):

OBSERVATION 3:
Using the same spatial k=15 nearest-neighbor graph on 228635 cells and 32 'leiden' clusters, we examined pairwise co-localization by comparing, for each directed pair (source cluster A, neighbor cluster B), the observed number of A→B neighbor contacts to the expectation under random mixing given the global abundance of B.
Considering only directed pairs with at least 50 observed neighbor contacts, we obtained 652 source–target combinations. Enrichment was defined as observed_contacts / expected_contacts, where expected_contacts = total_neighbors_from_source * global_frequency_of_target.
The top 10 enriched directed cluster–neighbor pairs (source → target) were:
- Source cluster 15 (code=15) had 2516 neighbors of cluster 30 (code=28), versus an expected 132.4 given global abundance, yielding an enrichment of 19.00.
- Source cluster 30 (code=28) had 2251 neighbors of cluster 15 (code=15), versus an expected 132.4 given global abundance, yielding an enrichment of 17.00.
- Source cluster 33 (code=31) had 1411 neighbors of cluster 28 (code=26), versus an expected 136.6 given global abundance, yielding an enrichment of 10.33.
- Source cluster 28 (code=26) had 1326 neighbors of cluster 33 (code=31), versus an expected 136.6 given global abundance, yielding an enrichment of 9.71.
- Source cluster 10 (code=10) had 6439 neighbors of cluster 30 (code=28), versus an expected 723.9 given global abundance, yielding an enrichment of 8.90.
- Source cluster 30 (code=28) had 6388 neighbors of cluster 10 (code=10), versus an expected 723.9 given global abundance, yielding an enrichment of 8.82.
- Source cluster 32 (code=30) had 1142 neighbors of cluster 15 (code=15), versus an expected 131.8 given global abundance, yielding an enrichment of 8.67.
- Source cluster 15 (code=15) had 1136 neighbors of cluster 32 (code=30), versus an expected 131.8 given global abundance, yielding an enrichment of 8.62.
- Source cluster 10 (code=10) had 3878 neighbors of cluster 33 (code=31), versus an expected 575.4 given global abundance, yielding an enrichment of 6.74.
- Source cluster 26 (code=25) had 1305 neighbors of cluster 30 (code=28), versus an expected 199.7 given global abundance, yielding an enrichment of 6.53.
Across all 32 clusters, global abundances spanned from 995 to 19947 cells (fractions 0.0044 to 0.0872 of all cells), indicating that enriched co-localization pairs involve both common and relatively rare clusters.

