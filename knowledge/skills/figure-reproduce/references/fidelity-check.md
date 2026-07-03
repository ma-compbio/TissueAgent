# Fidelity self-check — is the reproduction good enough?

The self-evaluation step (Workflow step 6). It produces a **B-level** for the
reproduction against the target, which the reflect-and-retry loop uses as its exit
condition. Two signals combine: a cheap **numeric prior** from image metrics, and
your **visual judgment** — and the visual judgment wins.

## 1. Run the metric prior

```bash
python scripts/compare_figures.py <target.png> <reproduced.png> --out compare_diff.png --json
```

It reports three metrics and writes a side-by-side diff you should open and look at:

| Metric | Meaning | Direction |
|---|---|---|
| **pHash Hamming** | perceptual-hash bit distance (0 = identical layout) | lower is better |
| **SSIM** | structural similarity on 512² grayscale, 0–1 | higher is better |
| **ORB good matches** | count of robust keypoint matches | higher is better |

The script also prints a **B-level prior** from the SSIM ladder:

```
SSIM ≥ 0.95 → B5      ≥ 0.85 → B4      ≥ 0.70 → B3      ≥ 0.40 → B2      < 0.40 → B1
```

**The prior is only a hint.** Metrics punish benign differences (a different
colormap, a legend moved, anti-aliasing, a stochastic embedding rotated) and reward
coincidental pixel overlap. When the metric and your eyes disagree, **trust your
eyes.** (In practice the metric-only prior is often one or two levels off — it once
scored a faithful panel B1 when a human read it as B4.)

**High SSIM does NOT confirm correctness.** SSIM is near-blind to color/palette and
label errors, so a plot with the **wrong colormap or wrong labels** can still land at
B5 on the ladder. Treat the prior as a ceiling hint, not a pass: down-grade by eye
whenever the colors, categories, or labels are off, even if SSIM is high.

## 2. Assign a B-level by eye (authoritative)

Compare the reproduced panel to the target and assign exactly one level:

- **B0 — No output.** No image was produced. (Deterministic; not a visual call.)
- **B1 — Incorrect.** Wrong content: different variable, wrong subset, wrong plot
  type, or an unrelated image.
- **B2 — Weak / partial.** Recognisably the same plot family, but key elements
  drift: values, color mapping, subsetting, or axis scales are notably off.
- **B3 — Qualitative recovery.** The same scientific claim is visually evident; the
  dominant pattern (cluster shape, ordering, trend direction) matches even if exact
  values differ. **This is the realistic ceiling for stochastic methods** (UMAP/
  t-SNE/clustering) and for pipelines with undocumented preprocessing.
- **B4 — Faithful.** Matches closely; only minor aesthetic differences (label
  styling, a colormap variant, layout spacing).
- **B5 — Near-exact.** Essentially identical; negligible differences.

Write the level and a one-line rationale into the repro note, citing concrete
elements ("legend order matches; our palette is viridis vs the paper's tab10 → B4").

## 3. Decide

- **At or above your target level** (usually B3 for stochastic/complex figures, B4
  for deterministic plots from released data) → done; record the level + any named
  deviation.
- **Below target** → enter `reflect-and-retry.md`. Diagnose *why* the level is low
  (wrong subset? wrong labels? wrong colormap? failed to run?) — that diagnosis
  selects the fix.

## 4. Common metric-vs-eye traps

- **Stochastic embedding** rotated/flipped run-to-run → low SSIM, but B3 by eye if
  the cluster structure matches. Don't chase pixels; set the seed and accept B3.
- **Different colormap** → low SSIM, high structural agreement → often B4.
- **Background underlay dropped** (spatial map on plain white vs the paper's
  histology) → looks close by metric on the foreground but is a real B2/B3 miss;
  restore the underlay.
- **Right picture, wrong panel** → if the target image is actually a *different*
  figure with the same number (main vs Extended Data), every metric is meaningless.
  Re-acquire the correct target first (see the playbook's figure-duplication trap).
- **Paper panel isn't the plot your data yields** → the PDF panel is a schematic/
  photo, or a different representation than your dataset produces. Comparing against
  it is meaningless. Use the **authors' reference plot / the caption's described
  plot** as the target of record (if you regenerate that reference from the repo's
  own code, note it's a consistency check, not an independent match); if the panel
  isn't derivable from the data at all, **honest-failure** — say so.
