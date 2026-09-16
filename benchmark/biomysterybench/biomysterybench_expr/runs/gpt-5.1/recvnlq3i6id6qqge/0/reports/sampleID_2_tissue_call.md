# Tissue-of-origin call for rnaseqSampleID_2

## Final call
- **Predicted tissue:** `brain_cortex`
- **Confidence:** High (very strong separation of cortex signal from all other tissues)

## Evidence from tissue score profile
Using the pre-computed tissue scores in `tissue_scores_by_sample.tsv`:

- **Top tissue by z-score:**
  - `score_brain_cortex` = **4.57** (z-score)
- **Runner-up tissues:**
  - `score_brain_cerebellum` = **0.03**
  - `score_spleen_lymphoid` = **0.01**
  - All remaining tissues have scores around **−0.18 to −0.26**.
- **Score gap:**
  - Top vs second-best: **4.57 − 0.03 ≈ 4.54**, which is near the upper tail of the gap distribution across all samples (median gap ≈ 3.62, 75th percentile ≈ 4.39).

This means rnaseqSampleID_2 is **strongly enriched** for the brain cortex marker panel, with essentially no competing tissue signal; even cerebellum, the next closest brain region, is barely above 0.

### Rawmean support (absolute signal)
The corresponding raw mean values (mean expression of the marker panel for each tissue) show that the cortex signal is also high in absolute terms:

- `rawmean_brain_cortex` = **247.2** (very high)
- Next highest rawmeans:
  - `rawmean_brain_cerebellum` ≈ **15.3**
  - `rawmean_spleen_lymphoid` ≈ **14.2**
  - Most other tissues are in the range **~0–4.5**.

So rnaseqSampleID_2 has **an order-of-magnitude higher cortex marker expression** than any other tissue panel, while non-cortex tissues are near background. This pattern is characteristic of a sample whose global expression is dominated by cerebral cortex–type neurons and glia.

## Evidence from top-expressed genes
From the original expression matrix `anonymizedGeneExp.tsv.gz`, the top expressed genes for `rnaseqSampleID_2` include (top 50 by expression):

- Very high mitochondrial transcripts (common in highly active tissues but not tissue-specific):
  - `MT-RNR2`, `MT-CO1`, `MT-CO2`, `MT-CO3`, `MT-ATP6`, `MT-ATP8`, `MT-ND1`, `MT-ND2`, `MT-ND3`, `MT-ND4`, `MT-ND4L`, `MT-ND5`, `MT-ND6`, `MT-CYB`, etc.
- **Canonical brain / neuron / glia-associated genes**, strongly supporting a cortical brain origin:
  - `SPARCL1` – enriched in astrocytes and specific brain vascular/astrocytic populations; often high in cortex.
  - `NRGN` (Neurogranin) – classic postsynaptic protein highly expressed in excitatory neurons of the cerebral cortex.
  - `KIF5A` – neuronally enriched kinesin heavy chain, associated with axonal transport in central neurons.
  - `MT3` (Metallothionein 3) – brain-specific metallothionein enriched in neurons.
  - `UCHL1` – neuron-specific ubiquitin carboxyl-terminal hydrolase (PGP9.5), broadly used as a neuronal marker.
  - `ALDOC` – glycolytic enzyme with strong expression in specific brain regions, including glial cells in cerebellum and cortex.
  - `ITM2C` – expressed in neurons and associated with amyloid precursor processing; enriched in brain tissue.
  - Additional broadly expressed but neuron/glia-compatible genes: `CPE`, `NDRG2` (glial/astrocyte-enriched), `SPARCL1`, `TSPAN7`, `PSAP`, `CKB`, `CALM1/2/3`.

This collection is highly characteristic of **central nervous system tissue**, particularly **cortical grey matter** where excitatory neurons, inhibitory interneurons, and astrocytes all contribute to the transcriptional profile.

## Alternative tissues and why they are less likely
- **Brain_cerebellum:**
  - Z-score is only **0.03** and rawmean ≈ **15.3**, far below the cortex panel (247.2).
  - While some genes (e.g. `ALDOC`) are also cerebellar, the overall marker panel is overwhelmingly cortical.
- **Blood/immune or spleen_lymphoid:**
  - Z-scores near **0** (`score_spleen_lymphoid` ≈ 0.01; `score_blood_immune` ≈ −0.22) with modest rawmeans (~14.2 and ~2.4), consistent with minor immune-related expression but not a primary hematopoietic profile.
  - The top genes are dominated by neuronal and glial markers, not immune markers.
- **Muscle, heart, liver, kidney, etc.:**
  - All have **negative z-scores** (~−0.18 to −0.26) and low rawmeans (~2–4).
  - No high-level expression of canonical markers like `MYH7`/`TNNT2` (heart), `ALB` (liver), `SLC5A2`/`UMOD` (kidney), or strong keratins (skin) appears among the top-expressed genes.

Given the combination of **very high cortex-specific score**, **large score gap**, **high absolute cortex marker expression**, and a **gene expression profile rich in well-known neuronal and glial markers**, alternative tissues (including cerebellum and non-CNS tissues) are markedly less consistent with the data.

## Consistency with other brain_cortex samples
Across all samples, those predicted as `brain_cortex` (269 samples):

- Have `score_brain_cortex` values with:
  - Median ≈ **4.27**, IQR roughly **3.76–4.55**.
- Non-brain-cortex samples have `score_brain_cortex` values centered near **−0.24** (median), with a maximum of ~3.07.

`rnaseqSampleID_2` has `score_brain_cortex` **4.57**, placing it at the **upper end of the distribution** for cortex-labeled samples and well-separated from non-cortex tissues. Its score profile is therefore **highly consistent with other samples called as brain cortex**, both in magnitude of the cortex score and in the lack of competing high scores for other tissues.

---
**Conclusion:** Based on the tissue score profile and the detailed gene expression pattern, `rnaseqSampleID_2` is best explained as **brain_cortex** (cerebral cortex), with **high confidence**.
