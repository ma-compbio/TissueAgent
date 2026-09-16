# Organ classification for Sample_X

## 1. Per-organ signature scores

Using mean z-score of organ-specific marker genes:

- **Heart**: mean_zscore = **3.10**, mean_expression ≈ 15.0 (top marker set by a wide margin)
- **Bone marrow**: mean_zscore = 1.68
- **Adipose**: mean_zscore = 1.47
- **Skeletal muscle**: mean_zscore = 0.60
- **Spleen**: mean_zscore = 0.44
- **Liver**: mean_zscore = 0.35
- **Lung**: mean_zscore = 0.07
- Other organs (skin, stomach, blood_immune, thymus, intestine, kidney, brain, ovary, pancreas, testis, placenta) all have mean_zscore ≤ 0 and/or substantially lower mean_expression of their markers.

The **score gap** between heart (3.10) and the next organs (bone marrow 1.68, adipose 1.47, skeletal muscle 0.60) is large (Δz ≈ 1.4–1.6 vs bone marrow/adipose, ≈ 2.5 vs skeletal muscle), indicating a very strong and specific cardiac signature.

## 2. Canonical marker expression

Expression values are MAS5+log2 normalized intensities; median across all genes is ≈7.1, 75th percentile ≈8.8, maximum ≈16.4.

### Heart
Key cardiac markers show very high and coherent expression with strong positive z-scores:

- **Sarcomeric / contractile genes**
  - MYH6: 14.9 (z ≈ 3.0)
  - TNNT2: 16.1 (z ≈ 3.5)
  - ACTC1: 16.3 (z ≈ 3.6)
  - MYL2: 16.4 (z ≈ 3.6)
  - MYL3: 16.0 (z ≈ 3.5)
  - TNNI3: 15.7 (z ≈ 3.3)
  - RYR2: 11.9 (z ≈ 1.9)
- **Cardiac hormones**
  - NPPA: 15.3 (z ≈ 3.2)
  - NPPB: 13.9 (z ≈ 2.6)

These values are near the global maximum expression range of the array (~16), far above the median (~7.1), and consistently high across multiple independent hallmark cardiac genes. This pattern is exactly what is expected for myocardium.

### Skeletal muscle
Several skeletal muscle markers are also expressed, but overall the skeletal muscle signature is weaker and more heterogeneous than the heart signature:

- Core contractile markers:
  - ACTA1: 14.2 (z ≈ 2.8)
  - CKM: 11.3 (z ≈ 1.6)
  - MYH7: 13.9 (z ≈ 2.6)
  - TNNT3: 7.2 (z ≈ 0.0)
- Other markers show low or negative z-scores, suggesting they are not collectively overexpressed:
  - MYH1: 4.6 (z ≈ −1.0)
  - MYH2: 6.7 (z ≈ −0.2)
  - MYH4: 6.0 (z ≈ −0.5)
  - MYOD1: 4.7 (z ≈ −1.0)
  - MYOG: 4.3 (z ≈ −1.1)
  - TNNI2: 6.2 (z ≈ −0.39)
  - TNNC2: 4.6 (z ≈ −1.0)

Interpretation: The sample exhibits a strong striated muscle program, but the **cardiac-specific markers (MYH6, TNNI3, NPPA, NPPB, high-level MYL2/MYL3, TNNT2)** are all very strongly expressed, while many fast-twitch skeletal markers are not uniformly high. This pattern is far more consistent with **heart** than with pure skeletal muscle.

### Bone marrow / blood / spleen (hematopoietic)
There is a clear hematopoietic component, but it is secondary to the heart signal.

**Bone marrow-associated markers:**

- HBA-A1: 15.6 (z ≈ 3.3)
- HBA-A2: 16.0 (z ≈ 3.5)
- HBB-B1: 16.0 (z ≈ 3.5)
- HBB-B2: 10.4 (z ≈ 1.3)
- LY6A: 13.0 (z ≈ 2.3)
- CD34: 11.0 (z ≈ 1.5)
- KIT, FLT3, MPO: moderate expression with slightly negative or modest z-scores.

**Blood/immune markers:**

- LYZ2: 12.7 (z ≈ 2.2)
- CD8A: 7.2 (z ≈ 0.0)
- PTPRC (CD45), ITGAM, ITGAX, NKG7: moderate expression (log2 ≈ 6–7), modest or absent z-score elevation.

Interpretation: The high hemoglobin expression (HBA/HBB) and some myeloid markers indicate **red cell / hematopoietic content**, which is common in vascular tissues and organ samples that contain blood. However, the overall bone marrow mean_zscore (1.68) is substantially below heart (3.10), and the pattern lacks the breadth of very high, lineage-defining markers expected for a primary bone marrow sample. Instead, it is consistent with **blood/hematopoietic cells present within a cardiac tissue sample**.

### Liver

- ALB: 11.1
- TTR: 10.0
- FGA: 8.5
- FGG: 7.7
- FGB: 5.5
- AFP: 3.2

These are clearly expressed above background but at substantially lower levels than the top cardiac markers, and the liver organ mean_zscore is modest (0.35). This likely reflects circulating serum proteins and hepatocyte-derived transcripts present in blood, not a liver tissue sample.

### Lung

- SCGB1A1 (club cell marker): 13.9 (high)
- SFTPD: 7.6
- SFTPB: 6.9
- SFTPC: 5.2
- SFTPA1: 4.2; SFTPA2 not detected

Lung-specific surfactant proteins are detectable, with one (SCGB1A1) quite high, but the **overall lung marker mean_zscore is low (0.07)**, much weaker than heart and bone marrow. This suggests possible minor airway or lung-derived contamination or shared expression, not a primary lung sample.

### Kidney

- AQP1: 12.8 (high)
- NPHS1: 7.4; SLC34A1: 6.8
- AQP2: 4.5; UMOD: 4.3; CDH16: 3.0

AQP1 is strongly expressed, but other canonical renal markers are only moderate or low, and kidney’s mean_zscore is negative (−0.39). AQP1 is also expressed in vascular endothelium and other tissues, so this isolated high expression does not outweigh the global evidence for heart.

### Brain

- MBP: 7.6
- SNAP25: 6.1
- SYP: 5.8
- RBFOX3: 5.2
- GFAP, NEUROD1/2: low

Brain markers are expressed around or slightly above the global median, but brain’s mean_zscore is negative (−0.45), and no coherent, high-level brain-specific program is apparent. These levels are compatible with minor neuronal/glial contamination or broadly expressed genes, not a brain sample.

### Adipose

Adipose has a moderately elevated mean_zscore (1.47). Top markers include Cebpa, Retn, Pparg, Lep, etc., with moderate expression. Given its lower score than heart and the clear dominance of cardiac markers, adipose likely represents stromal/adipocyte contribution within or adjacent to the cardiac tissue rather than the primary organ.

## 3. Resolving organ-of-origin

**Primary candidates based on scores and markers:**

- **Heart** (mean_zscore 3.10): Very strong, coherent overexpression of multiple independent, hallmark cardiac markers (sarcomeric genes, NPPA/NPPB, RYR2) at near-maximal array intensities.
- **Skeletal muscle** (0.60): Some shared striated muscle markers elevated, but many skeletal-specific markers are not strongly upregulated; overall score far below heart.
- **Bone marrow / hematopoietic** (1.68; spleen 0.44; blood_immune −0.25): Strong hemoglobin and some myeloid/lymphoid markers, but pattern compatible with blood content in a solid organ and lacks the dominance expected for pure marrow or blood.
- **Adipose** (1.47): Moderate signal consistent with stromal/adipose cells, not primary.

**Why heart over skeletal muscle?**

- Cardiac-specific genes **MYH6, TNNI3, NPPA, NPPB, high MYL2/MYL3 and TNNT2** are all exceptionally high and have large positive z-scores.
- Many skeletal-muscle–specific fast-twitch markers (MYH1, MYH2, MYH4, TNNC2, MYOD1, MYOG) have low or negative z-scores, indicating they are not globally enriched.
- The organ-level heart score is roughly **5-fold higher** than skeletal muscle in terms of mean_zscore (3.10 vs 0.60).

**Why not bone marrow or blood?**

- While hemoglobin genes and some hematopoietic markers are very high, they coexist with a **much stronger and broader heart-specific program**.
- Bone marrow’s mean_zscore (1.68) is significantly lower than heart’s (3.10), and classical stem/progenitor markers (KIT, FLT3, MPO, CD34) are not uniformly at the top of the expression distribution.
- The profile is better explained as **cardiac tissue with abundant intravascular blood** rather than a primary hematopoietic sample.

**Other organs (liver, lung, kidney, brain, etc.)** show at most moderate expression of some canonical markers and low or negative organ scores, consistent with background, shared, or blood-derived expression.

## 4. Final organ assignment

Integrating the organ-level scores with canonical marker expression, **Sample_X is best classified as originating from the heart (myocardium)**.

- Heart has by far the highest organ score and a strongly coherent set of hallmark markers at very high expression.
- Skeletal muscle, hematopoietic, adipose, and other organ signals are present but clearly secondary and plausibly represent tissue admixture (blood, stroma, neighboring tissues) rather than the primary organ of origin.

**Final label: `heart`.
