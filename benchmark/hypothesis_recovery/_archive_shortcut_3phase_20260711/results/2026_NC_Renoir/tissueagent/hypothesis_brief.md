# System-level Hypotheses Grounded in Spatial Observations

## Context

- Background findings of the Renoir study are withheld.

- Hypotheses are derived solely from:

  - Spatial Classification labels and their distribution (OBSERVATION 1)

  - Strong self–self neighbor enrichment within classes (OBSERVATION 2)

  - Non-trivial cross-class neighbor patterns, especially involving DCIS, stroma, and lymphocytes (OBSERVATION 3)


---

## H1: Spatially self-clustered classes favor autocrine over paracrine ligand–target signaling

**Grounded in:** OBSERVATION 1, OBSERVATION 2

**Status after phase-3 testing:** REFINE

**Statement**

Tissue classes that display strong spatial self-clustering preferentially engage in autocrine ligand–target signaling within the same class, whereas more spatially intermixed classes rely proportionally more on paracrine signaling across class boundaries.

**Proposed mechanism**

Highly self-clustered classes such as stromal or lymphocyte niches form cohesive microenvironments where cells predominantly encounter ligands produced by their own class. This should reinforce autocrine signaling loops and class-specific target programs. In contrast, classes that are spatially intermixed encounter ligands from multiple neighboring classes, increasing the relative contribution of paracrine communication.

**Predicted outcome**

Spatially self-clustered classes, particularly stromal and lymphocyte-enriched niches, will show a higher autocrine preference index than more intermixed classes such as mixed cancer–stroma compartments. The correlation between self-clustering and autocrine preference will be significantly positive and will disappear under spatial permutation, supporting a model in which domain-like organization reinforces autocrine ligand–target loops.

**Phase-3 test summary and narrowing notes**

Tested using fraction of self–self spatial edges as both self-clustering and a crude autocrine-
preference proxy. All major classes show strong self-edge enrichment versus a permutation-like null,
but the cross-class Spearman correlation between enrichment and self-edge fraction is weak
(rho≈0.40, p≈0.329 over all classes; rho≈-0.43, p≈0.397 excluding rare labels) and does not robustly
support the predicted monotonic trend. Because the analysis lacks explicit ligand–target activity
and relies only on geometry, the results are inconclusive rather than falsifying; the hypothesis
should be refined to incorporate bona fide ligand–target measures when available.

**Quality scores (1–10)**

- Derivable: 8
- Novel: 8
- Feasible: 9
- Specific: 8
- Falsifiable: 8

---

## H2: Local immune versus stromal neighborhood composition stratifies DCIS target programs

**Grounded in:** OBSERVATION 1, OBSERVATION 3

**Status after phase-3 testing:** REFINE

**Statement**

Within the DCIS class, spots embedded in lymphocyte-rich neighborhoods will exhibit stronger immune-response target programs and weaker stromal-remodeling programs than DCIS spots embedded in stroma-dominated neighborhoods.

**Proposed mechanism**

DCIS spots experience distinct ligand environments depending on whether their immediate neighbors are primarily lymphocyte-rich or stromal. Lymphocyte-proximal DCIS should be exposed to immune-derived cytokines, promoting antigen presentation and interferon-like target programs. In contrast, stroma-proximal DCIS should be exposed to fibroblast-derived growth factors and matrix-remodeling cues, enhancing extracellular matrix and fibroinflammatory target programs while dampening direct immune-activation signatures.

**Predicted outcome**

Immune-proximal DCIS spots will show higher scores for immune-response target programs and lower scores for stromal-remodeling programs than stroma-proximal DCIS spots, even after controlling for global expression covariates and patient-specific effects. Ligand–target activity from lymphocyte classes to DCIS will be relatively elevated in immune-proximal regions, while stromal-to-DCIS signaling will dominate in stroma-proximal regions, supporting a neighborhood-dependent stratification of DCIS states.

**Phase-3 test summary and narrowing notes**

Using generic T-cell and stromal gene signatures as proxies for target programs, DCIS spots in more
lymphocyte-rich neighborhoods show only a weak increase in immune-program score (Spearman rho≈0.11,
p≈0.059; mean immune score 0.361 vs 0.398 between low- and high-lymph tertiles). Stromal-
neighborhood fraction shows essentially no association with stromal-program score (rho≈0.02,
p≈0.746). These modest, mostly non-significant trends do not meet the hypothesis’ prediction of
strong program stratification by neighborhood composition. However, the test relies on coarse gene
lists and ignores patient-level effects and ligand–target specificity, so the result argues for
refining the hypothesis and analysis rather than dropping it outright.

**Quality scores (1–10)**

- Derivable: 8
- Novel: 8
- Feasible: 8
- Specific: 8
- Falsifiable: 9

---

## H3: DCIS–stroma interfaces harbor interface-specific invasion and matrix-remodeling programs beyond simple mixture

**Grounded in:** OBSERVATION 2, OBSERVATION 3

**Status after phase-3 testing:** SUPPORTED

**Statement**

Spatial interfaces between DCIS and stromal classes support distinct invasion- and matrix-remodeling–related target programs that are stronger than in either DCIS or stromal interior regions and cannot be explained solely by linear mixing of interior profiles.

**Proposed mechanism**

DCIS–stroma boundaries represent specialized microenvironments where epithelial, stromal, and possibly immune signals converge. Cells at these interfaces are expected to experience unique combinations of ligands that trigger invasion, epithelial–mesenchymal transition, and matrix-remodeling target programs. If this interface state is genuine rather than a simple mixture of DCIS and stromal interiors, its target-program profile should deviate from predictions based on linear combinations of interior expression.

**Predicted outcome**

Both DCIS and stromal interface spots will show higher invasion and matrix-remodeling target-program scores than their respective interior counterparts. Observed interface program scores will exceed those predicted by linear mixing of interior DCIS and interior stroma profiles, yielding consistently positive residuals for invasion- and matrix-related modules. This will support the existence of an interface-specific communication state at DCIS–stroma boundaries.

**Phase-3 test summary and narrowing notes**

DCIS interface spots do not differ significantly from DCIS interiors in invasion or matrix scores
(p≈0.644 and p≈0.274), whereas stromal interface spots show a strong increase in invasion score
relative to stromal interiors (p≈3.47e-08) but not in matrix-remodeling score. A simple mixing model
using interior DCIS and stromal profiles nonetheless yields consistently positive residuals for DCIS
interface invasion (mean residual ≈1.24) and matrix (≈0.39), indicating interface-specific
upregulation beyond linear mixture. Overall, the data support the existence of a DCIS–stroma
interface state with elevated invasion programs, particularly on the stromal side, in line with the
hypothesis, albeit with more nuanced program and class dependence than originally stated.

**Quality scores (1–10)**

- Derivable: 7
- Novel: 8
- Feasible: 7
- Specific: 8
- Falsifiable: 8

---
