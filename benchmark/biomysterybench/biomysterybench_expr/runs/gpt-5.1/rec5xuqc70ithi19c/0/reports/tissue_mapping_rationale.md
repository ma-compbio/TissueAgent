# Tissue group to true tissue mapping rationale

This report summarizes the evidence used to map each masked `Tissue_Group` to a biologically meaningful tissue or subregion. Expression values are group-level means.

## Whole_Blood → Peripheral_Whole_Blood


**Key evidence:** Strong enrichment of erythroid and leukocyte markers.



**Canonical blood/immune markers (mean expression):**


| Gene   |   Whole_Blood |       Liver |   Brain_Region_A |   Brain_Region_B |   Brain_Region_C |   Heart_Region_X |   Heart_Region_Y |
|:-------|--------------:|------------:|-----------------:|-----------------:|-----------------:|-----------------:|-----------------:|
| HBB    |   256730      | 23699.1     |      114.567     |       104.561    |      215.612     |       360.42     |       543.15     |
| HBA1   |    21211.5    |  1707.92    |        5.0057    |         4.8708   |        5.8592    |        12.093    |        14.3286   |
| HBA2   |   103662      |  6458.5     |       43.308     |        37.362    |       68.0878    |       114.027    |       180.079    |
| HBD    |    15452.3    |  1337.23    |        1.07198   |         1.30849  |        2.7589    |         3.13466  |        11.8073   |
| PTPRC  |      271.803  |    46.7322  |        1.07027   |         0.53255  |        2.02265   |         1.88868  |         3.62977  |
| LST1   |      133.398  |    17.2357  |        1.98214   |         1.417    |        3.56256   |         1.84088  |         2.36336  |
| MS4A1  |       20.6859 |     3.57897 |        0.0515582 |         0.039355 |        0.0825975 |         0.117604 |         0.253529 |
| CD3D   |       64.7302 |     8.3119  |        0.114021  |         0.179785 |        0.218455  |         0.343621 |         0.63486  |
| CD8A   |      128.35   |    13.7844  |        2.66566   |         3.9269   |        3.2332    |         0.39768  |         1.32835  |



## Liver → Liver


**Key evidence:** Classical hepatocyte secreted proteins and metabolic enzymes specifically enriched in Liver group.



**Canonical liver markers (mean expression):**


| Gene   |   Whole_Blood |     Liver |   Brain_Region_A |   Brain_Region_B |   Brain_Region_C |   Heart_Region_X |   Heart_Region_Y |
|:-------|--------------:|----------:|-----------------:|-----------------:|-----------------:|-----------------:|-----------------:|
| ALB    |     4931.38   | 34815.9   |         1.43577  |        2.64222   |         3.61141  |        1.83759   |         4.05973  |
| APOA1  |     3090.43   |  9459.66  |         0.81406  |        0.95658   |         0.90336  |       21.1873    |         5.5734   |
| APOB   |       43.1032 |   292.74  |         0.054069 |        0.0408801 |         0.055773 |        0.81222   |         3.84426  |
| TTR    |      674.695  |  5092.69  |         3.29104  |        2.12433   |         6.57334  |        0.259158  |         0.74541  |
| HP     |     1135.99   |  8032.69  |         0.436743 |        0.796049  |         1.10883  |        4.88074   |        17.2918   |
| FGA    |      494.121  |  2874.78  |         0.144304 |        0.302032  |         0.470095 |        0.065615  |         0.084233 |
| FGB    |      547.396  |  3944.43  |         0.210258 |        0.278336  |         0.713847 |        0.134037  |         0.127353 |
| FGG    |      460.831  |  3045.48  |         0.215619 |        0.242101  |         0.521187 |        0.108043  |         0.127237 |
| CYP3A4 |       53.7787 |   659.21  |         0.111975 |        0.498192  |         0.078791 |        0.0554899 |         0.116418 |
| CPS1   |       55.844  |   364.273 |         1.61171  |        0.75782   |         1.79136  |        0.4779    |         1.12188  |
| TAT    |      110.565  |   786.568 |         0.053002 |        0.083983  |         0.072356 |        0.0152698 |         0.038635 |



## Brain_Region_A/B/C → Cerebral_Cortex / Hippocampus / Cerebellum


All three brain groups show strong neuronal and glial marker expression, but regional markers differentiate cortex, hippocampus and cerebellum.



**General neuronal markers across brain groups:**


| Gene    |   Brain_Region_A |   Brain_Region_B |   Brain_Region_C |
|:--------|-----------------:|-----------------:|-----------------:|
| RBFOX3  |          74.328  |         221.236  |          30.231  |
| SLC17A7 |         494.307  |         588.73   |          92.1941 |
| GAD1    |          48.19   |          38.2303 |          54.264  |
| GAD2    |          26.0626 |          16.2259 |          52.398  |
| SYN1    |         279.4    |         267.84   |         116.759  |
| MAP2    |         149.673  |          90.734  |          86.201  |
| SNAP25  |         872.35   |        1421.91   |         552.55   |


**Regional / layer markers across brain groups:**


| Gene   |   Brain_Region_A |   Brain_Region_B |   Brain_Region_C |
|:-------|-----------------:|-----------------:|-----------------:|
| GFAP   |       1107.36    |        775.61    |       1111.99    |
| AQP4   |         55.746   |         21.793   |        102.867   |
| MBP    |        457.9     |        356.605   |        592.82    |
| OLIG2  |         27.696   |         12.5896  |         29.154   |
| SLC1A2 |        390.764   |         78.541   |        563.03    |
| SLC1A3 |        324.74    |        360.13    |        266.55    |
| PCP4   |        207.242   |        161.322   |        946.952   |
| RELN   |         15.7648  |         92.677   |          3.9902  |
| CALB1  |         40.2355  |         91.513   |         75.0684  |
| CALB2  |         81.542   |        254.777   |         28.2425  |
| RORB   |         10.5224  |          2.46688 |          6.0496  |
| CUX1   |         12.6341  |         33.8944  |          8.4677  |
| CUX2   |         13.5752  |          4.60277 |          2.52428 |
| TBR1   |         22.3957  |          2.66359 |          3.27286 |
| PROX1  |          3.199   |          8.242   |          2.4114  |
| ZBTB20 |          0.33016 |          1.32373 |          0.48853 |
| GRID2  |          1.9851  |          9.57723 |          1.79977 |


### Brain_Region_A → Cerebral_Cortex


Top group-specific markers (from group_marker_genes.tsv):


| Gene          |   Log2_FC |   Mean_in_group |   Mean_others |
|:--------------|----------:|----------------:|--------------:|
| MT-TA         |   5.7078  |       114.756   |     2.19561   |
| GS1-519E5.1   |   5.11846 |         1.95019 |     0.0561382 |
| HNRNPA1P46    |   5.06517 |         1.12242 |     0.0335255 |
| AC009487.4    |   4.7978  |         2.54317 |     0.0914302 |
| CTD-2023N9.2  |   4.63133 |         1.21692 |     0.0491003 |
| RP11-594C13.1 |   4.57862 |         2.45248 |     0.102636  |
| TBR1          |   4.49504 |        22.3957  |     0.99317   |
| KCNS1         |   4.41084 |        31.618   |     1.48641   |
| RP11-333B11.1 |   4.40476 |         3.98032 |     0.18791   |
| RP11-286B14.1 |   4.39216 |         4.67588 |     0.222685  |
| LINC01476     |   4.33535 |         3.1626  |     0.156665  |
| LINC00507     |   4.33382 |        13.9182  |     0.690198  |
| SATB2-AS1     |   4.32514 |         2.09362 |     0.104447  |
| MCHR2         |   4.32009 |         4.02624 |     0.201567  |
| CBLN2         |   4.2431  |        26.9827  |     1.4249    |
| EMX1          |   4.21755 |         8.47206 |     0.455386  |
| RP11-805F19.3 |   4.20318 |         4.51407 |     0.245066  |
| RP11-405M12.2 |   4.17316 |         1.23855 |     0.0686532 |
| SLC17A6       |   4.15315 |         2.64118 |     0.148447  |
| CTD-2023N9.3  |   4.15151 |        16.9211  |     0.952138  |


### Brain_Region_B → Hippocampus


Top group-specific markers (from group_marker_genes.tsv):


| Gene          |   Log2_FC |   Mean_in_group |   Mean_others |
|:--------------|----------:|----------------:|--------------:|
| NPAS4         |   8.48248 |       613.368   |     1.71491   |
| FGF3          |   7.10622 |        30.6067  |     0.22214   |
| CCDC155       |   6.78622 |        19.2808  |     0.17469   |
| RN7SKP73      |   6.69018 |         1.49776 |     0.0145033 |
| AC139099.7    |   6.49769 |         1.82729 |     0.0202202 |
| AF001550.7    |   6.3162  |         4.6515  |     0.0583742 |
| AC008060.8    |   6.27367 |         2.4725  |     0.0319567 |
| MTCO3P44      |   6.21574 |         1.14807 |     0.015446  |
| AC013733.3    |   6.17101 |         4.0731  |     0.0565273 |
| DUX4L9        |   6.12749 |         1.08262 |     0.0154843 |
| RP11-546B8.6  |   6.11761 |         8.5879  |     0.12368   |
| RP11-252A24.5 |   6.08635 |         1.10564 |     0.016271  |
| RP11-491F9.2  |   6.0767  |         2.18731 |     0.0324062 |
| RP11-491F9.3  |   6.07585 |        28.4833  |     0.422257  |
| TRIM43CP      |   6.03651 |         1.48482 |     0.0226195 |
| LINC02032     |   5.99694 |         4.22182 |     0.066105  |
| RP11-10N16.2  |   5.94066 |         2.8162  |     0.0458497 |
| ACTG1P18      |   5.93236 |         1.15105 |     0.0188473 |
| RP11-234O6.2  |   5.9052  |         2.30807 |     0.038512  |
| RP5-1097F14.3 |   5.90124 |         1.65543 |     0.0276977 |


### Brain_Region_C → Cerebellum


Top group-specific markers (from group_marker_genes.tsv):


| Gene          |   Log2_FC |   Mean_in_group |   Mean_others |
|:--------------|----------:|----------------:|--------------:|
| STOML3        |   9.1178  |         3.55289 |    0.00639417 |
| PIH1D3        |   8.14644 |         1.06768 |    0.00376705 |
| AP002856.7    |   7.86178 |         1.33007 |    0.005717   |
| C11orf88      |   7.37761 |         3.58565 |    0.0215608  |
| C1orf158      |   7.00081 |         1.1848  |    0.0092501  |
| RP11-60L3.6   |   6.59506 |         1.67601 |    0.0173357  |
| FAM183A       |   6.54648 |         9.3482  |    0.100008   |
| RP11-510C10.4 |   6.38243 |         1.19676 |    0.0143442  |
| C20orf85      |   6.30577 |         1.11649 |    0.0141123  |
| CCDC60        |   6.2808  |         1.31494 |    0.016911   |
| SLC47A2       |   6.22891 |         8.76455 |    0.116852   |
| RP11-493L12.6 |   6.21431 |         3.72998 |    0.0502348  |
| CCDC33        |   6.15935 |         1.52996 |    0.0214049  |
| LHX8          |   6.04178 |         1.92148 |    0.0291652  |
| MAP3K19       |   5.99084 |         1.84542 |    0.0290173  |
| C1orf87       |   5.97127 |         3.27529 |    0.0522048  |
| CFAP73        |   5.89319 |        11.7755  |    0.19813    |
| RP11-510C10.2 |   5.87954 |         1.35037 |    0.022936   |
| CTA-992D9.7   |   5.74357 |         1.51961 |    0.0283617  |
| CAPSL         |   5.7036  |         5.82927 |    0.111855   |



## Heart_Region_X/Y → Ventricular_Myocardium / Atrial_Myocardium


Both cardiac groups express sarcomeric genes, but atrial natriuretic/hormonal markers and regulatory light chains distinguish atrial from ventricular tissue.



**Canonical heart markers in the two cardiac groups:**


| Gene   |   Heart_Region_X |   Heart_Region_Y |
|:-------|-----------------:|-----------------:|
| MYH6   |         271.999  |         5850.87  |
| MYH7   |        4326.3    |          726.546 |
| TNNT2  |        2624.51   |         2697.86  |
| ACTC1  |        2956.5    |         5393.13  |
| TNNI3  |        6573.2    |         3055.76  |
| TTN    |          55.4869 |           66.589 |
| NPPA   |        9281.38   |        37670.9   |
| NPPB   |        1661.7    |         3777.53  |
| MYL2   |       18727.8    |          113.952 |
| MYL7   |        1491.77   |        12552.9   |
| MYL3   |        3690.63   |          134.427 |
| MYL4   |         197.592  |         3426.73  |
| SLN    |          28.1802 |          642.121 |


### Heart_Region_X → Ventricular_Myocardium


Top group-specific markers (from group_marker_genes.tsv):


| Gene          |   Log2_FC |   Mean_in_group |   Mean_others |
|:--------------|----------:|----------------:|--------------:|
| MYL2          |   9.55857 |     18727.8     |   24.8353     |
| CTD-2194D22.3 |   8.94658 |        12.8046  |    0.0259513  |
| RP11-23E10.4  |   8.03503 |         2.11845 |    0.00807567 |
| IRX4          |   7.30544 |         6.1118  |    0.0386369  |
| BANCR         |   7.1924  |        16.9629  |    0.115976   |
| MYL3          |   7.17253 |      3690.63    |   25.5831     |
| LINC01405     |   6.96716 |         7.13184 |    0.0569995  |
| GUCA1C        |   6.76551 |         4.93329 |    0.0453425  |
| CTD-2201G16.1 |   6.38096 |        80.2275  |    0.96264    |
| SLC6A10P      |   6.17162 |         1.05459 |    0.0146289  |
| IRX6          |   5.85803 |         6.87086 |    0.118458   |
| RP11-161D15.1 |   5.81691 |         4.67419 |    0.0829157  |
| RP11-1081M5.3 |   5.79819 |         4.69487 |    0.0843705  |
| RP11-973F15.2 |   5.65502 |         1.55533 |    0.0308658  |
| RP11-1081M5.1 |   5.54457 |         4.86691 |    0.104272   |
| DLK1          |   5.39189 |        11.6189  |    0.27672    |
| RP11-588F10.1 |   5.23723 |         1.79339 |    0.0475448  |
| LINC01936     |   5.18115 |         8.14814 |    0.224582   |
| RP11-19O2.1   |   5.17001 |         2.73084 |    0.0758513  |
| MYH7          |   5.13236 |      4326.3     |  123.345      |


### Heart_Region_Y → Atrial_Myocardium


Top group-specific markers (from group_marker_genes.tsv):


| Gene          |   Log2_FC |   Mean_in_group |   Mean_others |
|:--------------|----------:|----------------:|--------------:|
| PANCR         |   9.15008 |         2.207   |    0.00388367 |
| IGLV2-18      |   8.13478 |       376.519   |    1.3396     |
| GHRH          |   7.40861 |         9.4984  |    0.0559022  |
| MYBPHL        |   7.13881 |       137.209   |    0.973613   |
| MYH6          |   6.99905 |      5850.87    |   45.74       |
| SLN           |   6.48222 |       642.121   |    7.18247    |
| MYL4          |   6.38872 |      3426.73    |   40.8962     |
| BMP10         |   5.97925 |       488.982   |    7.75101    |
| SBK2          |   5.72094 |       107.304   |    2.03442    |
| MYL7          |   5.65011 |     12552.9     |  249.972      |
| LINC01880     |   5.61086 |        24.2219  |    0.495647   |
| LINC01985     |   5.58473 |         3.0587  |    0.0637322  |
| RP11-243M5.5  |   5.51341 |        33.3454  |    0.730019   |
| RP11-238I10.1 |   5.44924 |         4.17559 |    0.0955717  |
| MCOLN3        |   5.43398 |        12.8914  |    0.2982     |
| RP13-143G15.4 |   5.33266 |         3.06332 |    0.0760142  |
| PRR32         |   5.30865 |         4.46645 |    0.112693   |
| RP11-56H7.2   |   5.29624 |         1.10918 |    0.0282267  |
| SBK3          |   5.24556 |        17.0098  |    0.44836    |
| SPRR2F        |   5.24459 |         1.67149 |    0.0440875  |



## Ambiguities and alternative interpretations


- Brain_Region_A/B/C: All are clearly CNS tissue. The assignment to cortex vs hippocampus vs cerebellum is based on relative enrichment of cortical layer markers (RORB, CUX1/2, TBR1), hippocampal markers (PROX1, ZBTB20, RELN) and cerebellar markers (GRID2, PCP4, CALB1/2), but finer parcellation (e.g. specific cortical areas) is not attempted.


- Heart_Region_X/Y: Both are myocardium. Heart_Region_Y shows higher NPPA/NPPB, MYH6, MYL4, SLN and lower MYL2/MYL3/MYH7, consistent with atrial tissue, whereas Heart_Region_X is relatively enriched for ventricular contractile and regulatory genes, suggesting ventricular myocardium. Left vs right side cannot be determined from these markers alone.
