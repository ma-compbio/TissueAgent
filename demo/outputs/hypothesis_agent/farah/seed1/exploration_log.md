# Exploration log — Farah heart MERFISH

OBSERVATION 1:
The MERFISH developing human heart dataset contains 228635 cells and 238 genes.
The 'Populations' column has 27 cell-type / subtype categories; the 10 most abundant are: 
- vCM-LV-Compact: 30380 cells (13.288% of all cells)
- aCM-RA: 19947 cells (8.724% of all cells)
- vCM-Proliferating: 17584 cells (7.691% of all cells)
- vFibro: 16624 cells (7.271% of all cells)
- vCM-LV-Trabecular: 16511 cells (7.222% of all cells)
- BEC: 12248 cells (5.357% of all cells)
- VIC: 11596 cells (5.072% of all cells)
- vEndocardial: 10887 cells (4.762% of all cells)
- aCM-LA: 10441 cells (4.567% of all cells)
- vCM-RV-Compact: 9488 cells (4.150% of all cells)
There are 3 samples/sections (Sample_ID): R78_4C15 (79891 cells), R78_4C12 (75782 cells), R77_4C4 (72962 cells)
Spatial coordinates in `.obsm['spatial']` have shape (228635, 2) with x ranging from -10717.3 to 6634.4 and y from -4881.7 to 1712.3.
Example gene symbols in the panel include: ABCC9, ADAMTS6, ADAMTS8, ADGRL1, ADGRL2, ADGRL3, ADM, AGPS, AGT, ALDH1A2.

OBSERVATION 2:
Spatial concentration of each 'Populations' label was quantified using a same-label neighbor fraction (mean fraction of the 14 nearest non-self neighbors sharing the same label) divided by that label's global frequency.
Across all 27 labels, the 5 most spatially concentrated (restricted to labels with ≥500 cells) are:
- ncCM-IFT-like: 2027 cells (global frequency 0.887%), mean same-label neighbor fraction 0.722, clustering enrichment index 81.49.
- adFibro: 1562 cells (global frequency 0.683%), mean same-label neighbor fraction 0.535, clustering enrichment index 78.30.
- ncCM-AVC-like: 2292 cells (global frequency 1.002%), mean same-label neighbor fraction 0.619, clustering enrichment index 61.78.
- LEC: 1292 cells (global frequency 0.565%), mean same-label neighbor fraction 0.237, clustering enrichment index 41.85.
- VSMC: 4673 cells (global frequency 2.044%), mean same-label neighbor fraction 0.713, clustering enrichment index 34.89.
Across all labels (no minimum size filter), the median clustering enrichment index is 14.33, and the maximum is 81.49.

OBSERVATION 3:
For each of the 5 most spatially concentrated 'Populations' labels from OBSERVATION 2, non-self neighbor composition was quantified by pooling the 14 nearest non-self neighbors around all cells of that label and comparing to global label frequencies.
For focal label ncCM-IFT-like (n=2027 cells, clustering enrichment 81.49), there are 7877 pooled non-self neighbor positions.
- Neighbor Neuronal: 1234 occurrences (15.666% of non-self neighbors) vs global frequency 0.449%, enrichment 34.88.
- Neighbor aFibro: 3272 occurrences (41.539% of non-self neighbors) vs global frequency 3.244%, enrichment 12.80.
- Neighbor adFibro: 614 occurrences (7.795% of non-self neighbors) vs global frequency 0.683%, enrichment 11.41.
For focal label adFibro (n=1562 cells, clustering enrichment 78.30), there are 10170 pooled non-self neighbor positions.
- Neighbor LEC: 2349 occurrences (23.097% of non-self neighbors) vs global frequency 0.565%, enrichment 40.87.
- Neighbor WBC: 1065 occurrences (10.472% of non-self neighbors) vs global frequency 0.562%, enrichment 18.62.
- Neighbor ncCM-IFT-like: 877 occurrences (8.623% of non-self neighbors) vs global frequency 0.887%, enrichment 9.73.
For focal label ncCM-AVC-like (n=2292 cells, clustering enrichment 61.78), there are 12216 pooled non-self neighbor positions.
- Neighbor aFibro: 4099 occurrences (33.554% of non-self neighbors) vs global frequency 3.244%, enrichment 10.34.
- Neighbor ncCM-IFT-like: 367 occurrences (3.004% of non-self neighbors) vs global frequency 0.887%, enrichment 3.39.
- Neighbor BEC: 1771 occurrences (14.497% of non-self neighbors) vs global frequency 5.357%, enrichment 2.71.
For focal label LEC (n=1292 cells, clustering enrichment 41.85), there are 13810 pooled non-self neighbor positions.
- Neighbor adFibro: 2102 occurrences (15.221% of non-self neighbors) vs global frequency 0.683%, enrichment 22.28.
- Neighbor EPDC: 5957 occurrences (43.135% of non-self neighbors) vs global frequency 3.735%, enrichment 11.55.
- Neighbor Neuronal: 504 occurrences (3.650% of non-self neighbors) vs global frequency 0.449%, enrichment 8.12.
For focal label VSMC (n=4673 cells, clustering enrichment 34.89), there are 18764 pooled non-self neighbor positions.
- Neighbor adFibro: 1125 occurrences (5.996% of non-self neighbors) vs global frequency 0.683%, enrichment 8.78.
- Neighbor EPDC: 4246 occurrences (22.628% of non-self neighbors) vs global frequency 3.735%, enrichment 6.06.
- Neighbor VEC: 1257 occurrences (6.699% of non-self neighbors) vs global frequency 1.630%, enrichment 4.11.

OBSERVATION 4:
Pairwise cell-type co-localization was profiled by counting, for each 'Populations' label, the labels of all 14 nearest non-self neighbors and comparing these neighbor label fractions to global label frequencies. Only source–target pairs with at least 100 neighbor occurrences were considered.
The 10 most enriched directed source–target neighbor pairs (by observed/expected ratio) are:
- adFibro → LEC: 2349 neighbor occurrences, observed neighbor fraction 10.742% vs global frequency 0.565%, enrichment 19.01.
- LEC → adFibro: 2102 neighbor occurrences, observed neighbor fraction 11.621% vs global frequency 0.683%, enrichment 17.01.
- Neuronal → ncCM-IFT-like: 1306 neighbor occurrences, observed neighbor fraction 9.083% vs global frequency 0.887%, enrichment 10.25.
- ncCM-IFT-like → Neuronal: 1234 neighbor occurrences, observed neighbor fraction 4.348% vs global frequency 0.449%, enrichment 9.68.
- EPDC → LEC: 6002 neighbor occurrences, observed neighbor fraction 5.020% vs global frequency 0.565%, enrichment 8.88.
- LEC → EPDC: 5957 neighbor occurrences, observed neighbor fraction 32.933% vs global frequency 3.735%, enrichment 8.82.
- WBC → adFibro: 1071 neighbor occurrences, observed neighbor fraction 5.949% vs global frequency 0.683%, enrichment 8.71.
- adFibro → WBC: 1065 neighbor occurrences, observed neighbor fraction 4.870% vs global frequency 0.562%, enrichment 8.66.
- EPDC → Neuronal: 3629 neighbor occurrences, observed neighbor fraction 3.035% vs global frequency 0.449%, enrichment 6.76.
- Epicardial → LEC: 1219 neighbor occurrences, observed neighbor fraction 3.696% vs global frequency 0.565%, enrichment 6.54.

