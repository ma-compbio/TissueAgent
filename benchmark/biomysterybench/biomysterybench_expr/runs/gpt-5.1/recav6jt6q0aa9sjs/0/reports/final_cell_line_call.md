## Final cell line call: Caco-2

### Overview and lineage context

Expression profiling of sample_A, together with curated lineage markers, indicates a clear **colon / intestinal epithelial** origin. The lineage report shows very high scores for the colon/intestinal epithelium panel, driven by strong expression of classic intestinal enterocyte markers such as **MS4A12**, **CA1**, and **SI**, alongside epithelial markers (**EPCAM**, cytokeratins). A secondary EMT/mesenchymal signature (e.g. **VIM**) is present but does not override the core epithelial/intestinal identity.

### Candidate ranking and top competitors

In the ranked candidate panel, **Caco-2** is the **top-scoring line** (rank 1) with the highest composite **similarity_score** and the best categorical agreement fraction among colorectal lines, despite only modest absolute scores. The next-closest competitors are **DLD-1** (rank 2), **HCT15** (rank 3), and **SW620** (rank 4). 

- **Caco-2**: annotated as a highly differentiated, enterocyte-like colorectal line with strong brush-border and tight junction programs.
- **DLD-1 / HCT15**: moderately differentiated KRAS-mutant colon lines, with a more mixed goblet/enterocyte and stem-like program.
- **SW620**: a metastatic derivative of SW480 with pronounced EMT features (VIM-high, ZEB1-high).

Among these, Caco-2 has the best balance of correlation with the expected marker profile and categorical agreement, with fewer penalties for enterocyte markers and goblet markers than the others.

### Discriminative marker patterns

Using the candidate-specific marker panel (which embeds sample_A TPM and log2(TPM+1)), several genes help distinguish Caco-2 from its close competitors:

1. **Enterocyte / brush-border markers (favor Caco-2 and DLD-1/HCT15 over SW620)**
   - **MS4A12** (TPM ~1350, log2(TPM+1) ~10.4): extremely high in sample_A, a colon-specific enterocyte marker. This pattern is fully compatible with classic enterocyte-biased lines like **Caco-2**, **DLD-1**, and **HCT15**, and less characteristic of strongly EMT-dominated metastatic lines such as **SW620**.
   - **CA1** (TPM ~30, log2~4.95) and **SI** (TPM ~25, log2~4.72): robust expression supports an absorptive enterocyte program rather than a goblet-dominant phenotype.
   - **ALPI** is essentially off (TPM ≈ 0) despite high expected levels in Caco-2-type lines. This discrepancy suggests an atypical or less fully polarized enterocyte state in sample_A, but it affects several colorectal candidates similarly and is not sufficient to overturn the overall enterocyte-like assignment.

2. **Goblet vs absorptive bias (argues against goblet-heavy lines and mixed goblet competitors)**
   - **MUC2** is essentially off (TPM ≈ 0, log2=0), despite being expected high in strongly goblet-biased colorectal lines (e.g. HT29, LS174T, LoVo, and to a lesser extent DLD-1/HCT15). The absence of MUC2 expression argues against a primary goblet-cell-like program.
   - **KRT20** is also effectively off (TPM ≈ 0), whereas typical goblet-biased colorectal lines often show strong KRT20. This further supports an absorptive/enterocyte-skewed phenotype more compatible with Caco-2 than with goblet-heavy lines.

3. **Core epithelial / colorectal markers (shared across top colorectal candidates)**
   - **EPCAM** (TPM ~50, log2~5.67) and simple epithelial keratins **KRT8** (TPM ~140, log2~7.14), **KRT18** (TPM ~1.2, log2~1.15), and **KRT19** (TPM ~0.24, log2~0.31) confirm a classic epithelial carcinoma background and colorectal identity. These markers are largely shared among Caco-2, DLD-1, and HCT15 and thus support the colorectal assignment but are less discriminative between these three.

4. **EMT and stemness features (help separate Caco-2/DLD-1/HCT15 from strongly EMT SW620)**
   - **VIM** is high (TPM ~227, log2~7.83) across colorectal candidates, including Caco-2, indicating a hybrid epithelial–mesenchymal state in sample_A.
   - **ZEB1** (log2~2.2) and **SNAI1** (log2~3.74) are expressed at moderate levels, consistent with partial EMT. SW620 is annotated as EMT-very-high (ZEB1-high, VIM-high), but the overall ranked similarity_score and agreement metrics place SW620 below the more epithelial candidates.
   - Stem/crypt-associated markers **PROM1 (CD133)** and **SOX9** are essentially off (TPM ≈ 0), arguing against a highly stem-like/undifferentiated profile, which fits better with differentiated enterocyte-like Caco-2 than with some more stem-biased colorectal lines.

### Why Caco-2 over DLD-1 and HCT15

- All three top epithelial colorectal lines (Caco-2, DLD-1, HCT15) show good agreement with the high **MS4A12**, **CA1**, and **SI** signal in sample_A.
- Caco-2, however, has the **highest overall similarity_score** and best agreement fraction, indicating that its expected combination of high enterocyte markers, intact epithelial core (**EPCAM**, keratins), and relatively lower goblet bias most closely matches the observed pattern.
- DLD-1 and HCT15 carry expectations for more substantial goblet features (e.g., higher **MUC2**, more mixed goblet/enterocyte profile), which are not supported by the near-absent MUC2 and KRT20 in sample_A.
- SW620, while matching the EMT component (VIM, ZEB1, SNAI1), is penalized by its more strongly mesenchymal, metastatic profile and less enterocyte-differentiated expectation, and ranks lower accordingly.

Taken together, the **enterocyte-heavy, goblet-poor, epithelial-but-partially-EMT** profile of sample_A is most consistent with a **Caco-2–like colorectal enterocyte line**.

### Caveats and alternative possibilities

- Similar moderately enterocyte-like colorectal lines (e.g., certain DLD-1/HCT15 subclones or other colon cancer lines not represented in the reference panel) could show comparable marker patterns. Thus, the call should be interpreted as identifying the **closest available reference line**, not a definitive provenance.
- The lack of **ALPI** expression suggests that sample_A may represent a less fully polarized or variant Caco-2–like state rather than a textbook Caco-2 brush-border phenotype.

Nevertheless, within the evaluated candidate panel and based on similarity scores and discriminative markers, **Caco-2** is the **single best-matching cell line** for sample_A.
