OBSERVATION 1:
This dataset contains 228635 cells and 238 genes with 32 distinct labels in obs['leiden'] if available.
The recorded spatial range is: spatial extent x[-10717.3, 6634.4], y[-4881.7, 1712.3].
The 5 most abundant labels and their cell counts/fractions are:
- 0: 19947 cells (8.724%)
- 1: 17144 cells (7.498%)
- 3: 16624 cells (7.271%)
- 2: 15983 cells (6.991%)
- 4: 15703 cells (6.868%)

OBSERVATION 2:
Using a k=15 spatial nearest-neighbor graph on 228635 cells with 32 leiden labels, I computed for each label the fraction of same-label neighbors and compared it to the global label fraction.
The 5 most spatially self-enriched ("tight") labels by same-label neighbor enrichment over global abundance are: label 28: 2027 cells (0.8866% of all cells), same-label NN fraction 0.720, enrichment ratio 81.22; label 15: 1562 cells (0.6832% of all cells), same-label NN fraction 0.533, enrichment ratio 78.05; label 20: 3131 cells (1.3694% of all cells), same-label NN fraction 0.853, enrichment ratio 62.26; label 29: 2292 cells (1.0025% of all cells), same-label NN fraction 0.617, enrichment ratio 61.56; label 31: 1542 cells (0.6744% of all cells), same-label NN fraction 0.410, enrichment ratio 60.76.
This quantifies labels that form spatially compact domains relative to their overall abundance.

OBSERVATION 3:
For each of the spatially tight labels identified above, I examined the composition of their spatial neighbors using the same k-nearest-neighbor graph, comparing observed neighbor label fractions to global expectations.
For tight label 28 (2027 cells), the three most enriched non-self neighbor labels by enrichment over global abundance are: 33 (neighbors=1326, observed_frac=0.044, expected_frac=0.004, enrichment=9.71); 14 (neighbors=3529, observed_frac=0.116, expected_frac=0.032, enrichment=3.58); 15 (neighbors=664, observed_frac=0.022, expected_frac=0.007, enrichment=3.20).
For tight label 15 (1562 cells), the three most enriched non-self neighbor labels by enrichment over global abundance are: 30 (neighbors=2516, observed_frac=0.107, expected_frac=0.006, enrichment=19.00); 32 (neighbors=1136, observed_frac=0.048, expected_frac=0.006, enrichment=8.62); 20 (neighbors=1565, observed_frac=0.067, expected_frac=0.014, enrichment=4.88).
For tight label 20 (3131 cells), the three most enriched non-self neighbor labels by enrichment over global abundance are: 15 (neighbors=1232, observed_frac=0.026, expected_frac=0.007, enrichment=3.84); 24 (neighbors=1273, observed_frac=0.027, expected_frac=0.016, enrichment=1.66); 32 (neighbors=319, observed_frac=0.007, expected_frac=0.006, enrichment=1.21).
For tight label 29 (2292 cells), the three most enriched non-self neighbor labels by enrichment over global abundance are: 14 (neighbors=4406, observed_frac=0.128, expected_frac=0.032, enrichment=3.95); 23 (neighbors=1918, observed_frac=0.056, expected_frac=0.016, enrichment=3.44); 28 (neighbors=390, observed_frac=0.011, expected_frac=0.009, enrichment=1.28).
For tight label 31 (1542 cells), the three most enriched non-self neighbor labels by enrichment over global abundance are: 10 (neighbors=3809, observed_frac=0.165, expected_frac=0.037, enrichment=4.41); 23 (neighbors=891, observed_frac=0.039, expected_frac=0.016, enrichment=2.38); 18 (neighbors=1226, observed_frac=0.053, expected_frac=0.024, enrichment=2.22).

OBSERVATION 4:
Using all edges in the spatial k-nearest-neighbor graph, I quantified pairwise co-localization between all leiden labels by comparing observed neighbor counts to expectations from global label frequencies, symmetrized across label pairs. I report the top 10 most strongly co-localized non-identical label pairs with at least 500 observed neighbor edges.
- 30–15: observed neighbor edges≈4767, expected≈264.8, enrichment≈18.00
- 15–30: observed neighbor edges≈4767, expected≈264.8, enrichment≈18.00
- 33–28: observed neighbor edges≈2737, expected≈273.2, enrichment≈10.02
- 28–33: observed neighbor edges≈2737, expected≈273.2, enrichment≈10.02
- 10–30: observed neighbor edges≈12827, expected≈1447.8, enrichment≈8.86
- 30–10: observed neighbor edges≈12827, expected≈1447.8, enrichment≈8.86
- 32–15: observed neighbor edges≈2278, expected≈263.6, enrichment≈8.64
- 15–32: observed neighbor edges≈2278, expected≈263.6, enrichment≈8.64
- 10–33: observed neighbor edges≈7562, expected≈1150.8, enrichment≈6.57
- 33–10: observed neighbor edges≈7562, expected≈1150.8, enrichment≈6.57

