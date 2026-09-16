# Drug assignment rationale

**Important limitation upfront:** the formal pathway enrichment analysis is effectively uninformative: only three genes (ACTB, GAPDH, STAT1) map into the curated MoA sets, none of them are significantly differentially expressed at adj.P.Val < 0.05 and |logFC| ≥ 1 in any group, and all Fisher tests return p = 1 and FDR = 1.0. In addition, most probes in the DE tables cannot be mapped to recognizable gene symbols with the available platform annotation extract. As a result, the assignments below are necessarily **hypothesis‑level and pattern‑based**, drawing mainly on (i) the *extent and symmetry* of differential expression and (ii) very generic expectations for how broad or focused certain drug classes tend to be.

---

## Group A → Rapamycin

**Relative strength/extent of DE.** Group A has a modest but clearly non‑trivial signature: 36 probes meet adj.P.Val < 0.05 and |logFC| ≥ 1.0 (19 up, 17 down), with median |logFC| among significant probes ~1.5 and a maximum |logFC| around 2.4. The overall logFC distribution is fairly tight (std ~0.39) and roughly centered on zero. This looks like a *moderate, balanced* perturbation—stronger than a nearly null profile, but far less extensive than Group B.

**Qualitative MoA hints.** There is no robust enrichment for any curated pathway, and the subset of probes that can be mapped to ACTB, GAPDH, or STAT1 do not show large or significant changes. Among the top significant probes, logFC values are in the 1–2 range without any clear cluster of classic stress‑response, histone, or chaperone symbols. The signature therefore appears relatively *targeted* rather than globally re‑wiring transcription.

**Comparison to other groups / why Rapamycin.** mTOR inhibition by Rapamycin is often cytostatic and pathway‑focused (affecting growth, translation, metabolism) rather than causing the very broad histone‑acetylation‑like or DNA‑damage‑like upheavals associated with HDAC inhibitors or anthracyclines. Among the four groups, A best matches this expectation: it shows a clear but limited pattern of both up‑ and down‑regulation, with moderate effect sizes and no obvious hallmarks of overwhelming stress or apoptosis. Assigning Group A to **Rapamycin** is thus weakly supported by the *scale and balanced nature* of the transcriptomic change, while acknowledging that no direct mTOR/PI3K markers can be confirmed here.

---

## Group B → Trichostatin A

**Relative strength/extent of DE.** Group B shows by far the largest and most widespread transcriptional response: ~1,412 probes pass adj.P.Val < 0.05 and |logFC| ≥ 1.0, with both strong up‑ and down‑regulation (≈644 up, 768 down). The maximum |logFC| exceeds 4, and the logFC standard deviation (~0.56) is higher than in the other groups. Volcano and summary statistics both point to very broad reprogramming rather than a narrowly focused pathway effect.

**Qualitative MoA hints.** Despite the mapping limitations, it is clear that many probes show sizeable changes in both directions, suggesting global reshaping of gene expression programs (activation of some sets, repression of others). This is exactly the sort of pattern expected for a chromatin‑modifying agent such as an HDAC inhibitor, which can de‑repress large sets of genes and secondarily trigger feedback repression elsewhere. There is no convincing specific signal for heat‑shock (HSPs), classic DNA‑damage markers, or STAT1/IFN‑like patterns in the restricted gene‑mapped subset.

**Comparison to other groups / why Trichostatin A.** Among the candidate drugs, **Trichostatin A** (an HDAC inhibitor) is the one most strongly associated with **widespread transcriptional reprogramming** rather than isolated pathway inhibition or purely stress‑chaperone induction. Group B is the only group with such a massive and symmetric up/down response, so it is the most natural match for Trichostatin A. This assignment is comparatively well supported in a relative sense (by the magnitude and breadth of DE), even though we lack direct enrichment for histone/HDAC gene sets due to annotation constraints.

---

## Group C → Doxorubicin

**Relative strength/extent of DE.** Group C has an intermediate profile: 24 probes meet the significance/effect‑size thresholds (all up‑regulated), with a median |logFC| for significant probes ~1.6 and a maximum |logFC| across all probes of ~4.8 (the largest single‑probe effect observed among the four groups). The global variance in logFC (std ~0.49) is between that of Groups A and B. This suggests a **focused but high‑amplitude** response: a relatively small set of strongly induced probes rather than the thousands‑of‑probes shift seen in Group B.

**Qualitative MoA hints.** The fact that all threshold‑passing probes are up‑regulated, and some with very large fold‑changes, is consistent with an induced stress‑response or damage‑response program where sentinel genes become strongly activated. With our current annotation snapshot we cannot confidently identify canonical p53 targets (e.g., CDKN1A, GADD45, BAX) or other DNA‑damage markers, and enrichment for the DNA‑damage/p53 set is formally non‑significant. Nonetheless, the pattern "few but very strongly induced genes" is qualitatively more in line with such a stress/apoptotic signature than with chromatin‑wide de‑repression.

**Comparison to other groups / why Doxorubicin.** Among the four drugs, **Doxorubicin** (a DNA‑damaging anthracycline) is the most likely to provoke a *high‑amplitude, stress/apoptosis‑skewed* transcriptional response without necessarily re‑wiring the entire transcriptome at the time point sampled. Group C’s combination of (i) modest number of significant probes, (ii) large maximum logFC, and (iii) exclusively up‑regulated significant hits, sets it apart from the more balanced Rapamycin‑like pattern of Group A and the HDAC‑like global reprogramming of Group B. On that relative basis, Group C is most plausibly mapped to Doxorubicin, while recognizing that this is an inferential match rather than one anchored by explicit p53‑pathway enrichment.

---

## Group D → Geldanamycin

**Relative strength/extent of DE.** Group D shows the weakest transcriptomic perturbation: only 5 probes meet the adj.P.Val and |logFC| ≥ 1.0 thresholds, all up‑regulated, with a median |logFC| ~1.8 and a maximum |logFC| ~3.5 among all probes. The overall logFC variability is modest (std ~0.46), and volcano plots indicate just a handful of strong outliers against an otherwise tight cloud near zero. This looks like a **subtle, low‑coverage** response compared to all other groups.

**Qualitative MoA hints.** With so few significant probes and near‑complete lack of reliable gene‑symbol annotation among them, there is no visible cluster of classic heat‑shock or HSP90‑client genes, nor any obvious DNA‑damage or mTOR‑pathway markers, and enrichment analysis provides no further guidance. However, it is plausible that an HSP90 inhibitor such as Geldanamycin might produce a **relatively contained transcriptional footprint** at the assayed time and dose, particularly if much of its effect is post‑transcriptional (through destabilization of client proteins) combined with a limited chaperone/stress induction.

**Comparison to other groups / why Geldanamycin.** After assigning the strongly reprogrammed profile (Group B) to Trichostatin A, the moderately broad, balanced change (Group A) to Rapamycin, and the focused high‑amplitude induction (Group C) to Doxorubicin, **Geldanamycin** is the remaining candidate. Among the remaining patterns, Group D’s very small, mostly up‑regulated signature is the least inconsistent with an HSP90‑inhibitor scenario in which only a subset of stress/heat‑shock related transcripts are substantially induced. This mapping is therefore the most speculative of the four, driven primarily by relative process‑of‑elimination and the notion that HSP90 inhibition might yield a narrower transcriptomic response under the specific experimental conditions.

---

## Overall limitations

- **Non‑informative enrichment:** ORA against mTOR, HDAC/chromatin, HSP90/heat‑shock, and DNA‑damage/p53 gene sets is formally negative in all groups (FDR = 1.0), because almost no genes from those sets are represented in the small annotated overlap, and none are significantly DE.
- **Sparse probe‑to‑gene mapping:** The vast majority of significantly changing probes cannot be linked to recognizable gene symbols with the provided GPL570 mapping subset, which prevents direct identification of hallmark markers (HSPs, histones, canonical p53 targets, etc.).
- **Pattern‑based, relative reasoning:** The assignments rely on global patterns (breadth and symmetry of DE, magnitude of logFC, relative differences between groups) and generic expectations for Rapamycin, Trichostatin A, Geldanamycin, and Doxorubicin responses. They should be viewed as **coherent hypotheses** rather than definitive identifications.
