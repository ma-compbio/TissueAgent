OBSERVATION 1:
Total cells: 228635.
Cell-type column 'Populations' has 27 unique labels; top 10 (label: count, percent of cells):
vCM-LV-Compact: 30380 (13.29%), aCM-RA: 19947 (8.72%), vCM-Proliferating: 17584 (7.69%), vFibro: 16624 (7.27%), vCM-LV-Trabecular: 16511 (7.22%), BEC: 12248 (5.36%), VIC: 11596 (5.07%), vEndocardial: 10887 (4.76%), aCM-LA: 10441 (4.57%), vCM-RV-Compact: 9488 (4.15%)
Cluster column 'leiden' has 32 unique labels; top 10 (label: count, percent of cells):
0: 19947 (8.72%), 1: 17144 (7.50%), 3: 16624 (7.27%), 2: 15983 (6.99%), 4: 15703 (6.87%), 5: 14036 (6.14%), 6: 11596 (5.07%), 7: 10887 (4.76%), 8: 10441 (4.57%), 9: 10149 (4.44%)
Metadata column 'Sample_ID' has 3 unique values; top 10 (value: count, percent of cells):
R78_4C15: 79891 (34.94%), R78_4C12: 75782 (33.15%), R77_4C4: 72962 (31.91%)
Metadata column 'Batch' has 3 unique values; top 10 (value: count, percent of cells):
R78_4C15: 79891 (34.94%), R78_4C12: 75782 (33.15%), R77_4C4: 72962 (31.91%)

OBSERVATION 2:
Rare-but-tight analysis on cell-type column 'Populations' using k=20 nearest neighbors; top 5 labels by same-label neighbor fraction / global frequency:
ncCM-IFT-like: cells=2027 (0.89% of total), same-label-NN-fraction=0.707, concentration-ratio=79.69
adFibro: cells=1562 (0.68% of total), same-label-NN-fraction=0.521, concentration-ratio=76.23
ncCM-AVC-like: cells=2292 (1.00% of total), same-label-NN-fraction=0.605, concentration-ratio=60.34
LEC: cells=1292 (0.57% of total), same-label-NN-fraction=0.213, concentration-ratio=37.63
VSMC: cells=4673 (2.04% of total), same-label-NN-fraction=0.691, concentration-ratio=33.81
For each of these concentrated labels, the top 3 non-self neighboring cell-type labels (by enrichment over global frequency) among k-nearest neighbors are:
ncCM-IFT-like: Neuronal: local=15.29% vs global=0.45%, enrichment-ratio=33.68; aFibro: local=40.92% vs global=3.06%, enrichment-ratio=13.39; adFibro: local=8.36% vs global=0.66%, enrichment-ratio=12.67
adFibro: LEC: local=22.82% vs global=0.56%, enrichment-ratio=40.61; WBC: local=9.89% vs global=0.54%, enrichment-ratio=18.42; Epicardial: local=9.06% vs global=0.78%, enrichment-ratio=11.55
ncCM-AVC-like: aFibro: local=32.81% vs global=3.06%, enrichment-ratio=10.74; ncCM-IFT-like: local=2.78% vs global=0.94%, enrichment-ratio=2.97; BEC: local=15.12% vs global=5.40%, enrichment-ratio=2.80
LEC: adFibro: local=15.20% vs global=0.66%, enrichment-ratio=23.03; EPDC: local=41.71% vs global=3.60%, enrichment-ratio=11.57; Neuronal: local=3.76% vs global=0.45%, enrichment-ratio=8.27
VSMC: adFibro: local=6.18% vs global=0.66%, enrichment-ratio=9.37; EPDC: local=22.91% vs global=3.60%, enrichment-ratio=6.36; VEC: local=6.74% vs global=1.39%, enrichment-ratio=4.86

OBSERVATION 3:
Pairwise co-localization using k-nearest-neighbor edges on cell-type column 'Populations' (k=20); top 10 center→neighbor label pairs ranked by observed/expected edge count (require observed count ≥50):
adFibro → adFibro: observed_edges=16269, expected_edges=206.2, enrichment-ratio=78.91
ncCM-IFT-like → ncCM-IFT-like: observed_edges=28642, expected_edges=379.8, enrichment-ratio=75.42
ncCM-AVC-like → ncCM-AVC-like: observed_edges=27730, expected_edges=464.2, enrichment-ratio=59.74
LEC → LEC: observed_edges=5495, expected_edges=145.2, enrichment-ratio=37.84
VSMC → VSMC: observed_edges=64578, expected_edges=1988.2, enrichment-ratio=32.48
Epicardial → Epicardial: observed_edges=11639, expected_edges=369.6, enrichment-ratio=31.49
Neuronal → Neuronal: observed_edges=2638, expected_edges=93.2, enrichment-ratio=28.30
VEC → VEC: observed_edges=27829, expected_edges=1034.2, enrichment-ratio=26.91
vCM-His-Purkinje → vCM-His-Purkinje: observed_edges=68643, expected_edges=2644.2, enrichment-ratio=25.96
adFibro → LEC: observed_edges=3417, expected_edges=175.6, enrichment-ratio=19.46

