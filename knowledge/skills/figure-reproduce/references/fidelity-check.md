# Fidelity self-check — is the reproduction good enough?

The self-evaluation steps (Workflow steps 8–10). They produce a **B-level** for the
reproduction against the target, which the reflect-and-retry loop uses as its exit
condition. Two signals combine: a cheap **numeric prior** from image metrics, and
your **visual judgment** — and the visual judgment wins.

The order matters: run the metrics, **then open the side-by-side and name what you
see**, then score from that list. Scoring straight off the numbers, or off a glance,
is how a wrong palette or a reordered legend gets waved through.

## 1. Run the metric prior

```bash
python scripts/compare_figures.py <target.png> <reproduced.png> --out compare_diff.png --json
```

It reports five metrics and writes the side-by-side diff that §2 makes you open.
Three are computed on **grayscale** and are blind to color and labels:

| Metric | Meaning | Direction |
|---|---|---|
| **pHash Hamming** | perceptual-hash bit distance (0 = identical layout) | lower is better |
| **SSIM** | structural similarity on 512² grayscale, 0–1 | higher is better |
| **ORB good matches** | count of robust keypoint matches | higher is better |

The script also reports two signals that are **not** grayscale, and which exist
because pHash/SSIM/ORB are blind to them:

| Metric | What it measures | Reading |
|---|---|---|
| **Palette mean dE** | share-weighted CIELAB distance between the two palettes | ≤2.3 imperceptible; >8 a real color error; >30 an unrelated palette |
| **Text diff** | OCR'd on-panel strings: exact / near-miss / missing | near-misses are paraphrased labels — copy the target's text verbatim |

The **B-level prior** is the *minimum* across every ladder that could be computed:

```
SSIM    ≥ 0.95 → B5     ≥ 0.85 → B4     ≥ 0.70 → B3     ≥ 0.40 → B2     < 0.40 → B1
dE(LAB) ≤ 3.0  → B5     ≤ 8.0  → B4     ≤ 18.0 → B3     ≤ 32.0 → B2     > 32   → B1
text    ≥ 0.95 → B5     ≥ 0.80 → B4     ≥ 0.55 → B3     ≥ 0.25 → B2     < 0.25 → B1
```

Taking the minimum is what makes the prior fail in the safe direction: a figure with
the wrong palette but identical structure scores SSIM ≈ 0.99 and is still floored to
B1, with `limited_by: color` naming the cause. Read that field — it tells you which
fix to apply.

**A signal that could not be computed is excluded, not passed.** If OCR is missing,
the text ladder is absent and the prior is silently more permissive; check
`which_metrics_computed` and verify labels yourself.

**Still only a prior.** It can punish benign differences (a stochastic embedding
rotated, anti-aliasing, a legend moved) and reward coincidental overlap. When the
metric and your eyes disagree, **trust your eyes** — but a *color* or *text*
disagreement now deserves a second look at the numbers first, because those are
measured rather than inferred.

**Category ORDER is still unmeasured** by `compare_figures.py`. Verify it against
the legend/tick order in `spec.yaml` from `extract_reference_spec.py`, or against
the plotted-data CSV's category sequence.

## 2. Open the side-by-side and name the differences

`compare_figures.py` wrote `compare_diff.png` — the target and your reproduction at
matched height. **`read()` it.** The file is on disk, not returned inline, so it
never reaches your context unless you open it explicitly.

Then go through the panel deliberately. Unstructured looking produces "looks close
enough"; this checklist produces a list you can act on:

| Dimension | Ask |
|---|---|
| **Color** | Same hues? Is each category bound to the *same* color as the target, not just drawn from the same palette? |
| **Order** | Legend / bars / heatmap rows / facets in the target's sequence? |
| **Text** | Axis, tick, legend, title wording — identical, including units and capitalisation? Any label the target has that you dropped? |
| **Marks** | Marker size, opacity, line width, point density comparable? |
| **Geometry** | Aspect ratio, axis limits, orientation (y often flipped on spatial), tick placement? |
| **Underlay** | Background / histology image present if the target has one? (A spatial map on white reads as a clear miss.) |
| **Continuous scale** | Colorbar range, direction (`_r`), ticks and its label? |
| **Presence** | Anything visible in one panel and absent from the other — an annotation, a subpanel, a dendrogram, a scale bar? |

Write the differences down as a list. Some will be real errors; some will be benign
(§6). Assigning the level from an explicit list is what keeps a high SSIM from
talking you into a level the picture doesn't deserve.

## 3. Assign a B-level by eye (authoritative)

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

## 4. Reflect — what would make it closer?

Do this **whether or not** the level is acceptable — and do it **once**. Take the
difference list from §2 and ask what would close each gap, then name the top 2–3.

- **Cheap** (a plotting-cell re-run: palette, category order, label text, marker
  size, aspect, axis limits, colorbar range, underlay) → apply them in **one batched
  polish pass**, not one fix per cycle.
- **Expensive** (re-running the analysis, re-prepping data) or **unsupported by the
  data** → don't chase it; record it as a named residual gap in the repro note.

### Stopping (this loop must terminate)

Reflection re-renders the figure, so it consumes the same **≤3 reproduction
attempts** as any repair (`reflect-and-retry.md` §3). It is cheap, not free. Stop at
the **first** of these:

| Stop when | Why |
|---|---|
| You cannot name a **concrete difference from the target** | "Could look nicer" is a preference, not a defect. Preferences are unbounded; differences are finite. |
| A pass didn't improve the B-level **or** shorten the difference list | You are polishing noise. |
| You are at **B5** | Nothing left to close. |
| The attempt budget is spent | Keep the best attempt, name the gap. |
| Remaining items are **expensive or unsupported** | Record them; don't chase them. |

Default to **one** polish pass. Take a second only if the first closed a difference
you had named in §2, and never a third.

Two failure modes bound this from both sides: shipping a figure that was one cheap
fix from right, and polishing a finished figure forever. The difference list is what
separates them — when it is empty of *real* differences, you are done. And never
tweak data or thresholds to force a pixel match: that's over-matching (§6).

## 5. Decide

- **At or above your target level** (usually B3 for stochastic/complex figures, B4
  for deterministic plots from released data) → done; record the level + any named
  deviation.
- **Below target** → enter `reflect-and-retry.md`. Diagnose *why* the level is low
  (wrong subset? wrong labels? wrong colormap? failed to run?) — that diagnosis
  selects the fix.

## 6. Common metric-vs-eye traps

- **Stochastic embedding** rotated/flipped run-to-run → low SSIM, but B3 by eye if
  the cluster structure matches. Don't chase pixels; set the seed and accept B3.
- **Different colormap/palette** → SSIM stays *high* (it is grayscale-blind), so the
  structural metrics will not flag it. The palette-dE ladder is what catches this;
  if dE is large the figure is not B4 no matter how good SSIM looks. Fix it by
  re-extracting the spec, not by re-judging the picture.
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

---

## The two metric passes

**The script reports TWO passes — you must read both before concluding.**

   - **Pass 1** (pHash / SSIM / ORB / palette dE / text) compares the images in
     grayscale after resizing both to a *square*. It is sensitive to content but
     structurally blind to shape, canvas and orientation.
   - **Pass 2** (`pass2_geometry` in the JSON) measures what pass 1 cannot:
     canvas size and aspect, panel **background colour** (probed inboard, since
     `bbox_inches="tight"` makes corners lie), an **orientation flip test** that
     re-scores the reproduction mirrored to see if a flip fits better, **content
     bbox/extent**, and **column density** — which exposes a legend or colorbar
     block the target does not have.

   Pass 2 emits a `findings` list. **A non-empty `findings` is a defect list, not
   advice:** fix each entry and re-render, or name it explicitly in the repro note
   as an accepted deviation. `"clean": true` is what lets you move on. Pass 2 also
   feeds the `geometry` ladder into the B-level minimum, so a wrong-shaped or
   wrong-background figure can no longer report a good B-level on pass-1 strength
   alone. **Concluding on pass 1 while pass 2 lists defects is a failed step.**

---

## Structural defects and how to test for them

**Structural defects (never "good enough" — fix or explain why you cannot):**

   > **orientation** — the panel is flipped/mirrored/rotated vs the target, or an
   > axis runs the wrong way (image-convention y-axis, `invert_yaxis()`,
   > `origin="upper"`, a transposed matrix) · **canvas/background** — the panel
   > background is a different colour from the target's (a dark facecolor behind a
   > light-background figure recolours every gap between markers and tanks SSIM on
   > its own) · **canvas shape** — the figure's width:height ratio differs from the
   > target's (portrait reproduced as landscape, or a squashed/stretched panel);
   > **the metrics cannot see this**, because `compare_figures.py` resizes both
   > images to a square before comparing · **wrong plot primitive** · **wrong panel
   > count or facet layout** · **a category present in one figure and absent in the
   > other** · **axes swapped** · **a colormap running in the opposite
   > direction**.

   These change what the figure *means*, are usually a one-line fix, and are
   exactly what a global metric hides: pHash/SSIM read a mirrored panel as
   "different everywhere", producing a uniformly bad score with no clue why — which
   is indistinguishable from "hard to match" unless you name it from the
   side-by-side. If your list says the orientation is wrong and you stop anyway,
   you have shipped the wrong figure with a low score attached.

   **Orientation is not a judgement call — test it.** Re-render with the axis
   flipped (or the transform removed) and re-run the metrics. Whichever version
   scores better *is* the right orientation. That is one cheap attempt, and it
   settles the question with a measurement instead of an opinion.

   **Background is not a judgement call either — sample it.** Do not assert the
   backgrounds match from looking; read the pixels of both images:

   ```python
   from PIL import Image; import numpy as np
   for p in (target_path, repro_path):
       a = np.array(Image.open(p).convert("RGB")); h, w, _ = a.shape
       # Corners alone are NOT enough: bbox_inches="tight" leaves a white figure
       # margin around the axes, so a black *axes* canvas still shows white
       # corners. Probe inboard, where the panel background actually is.
       print(p, "corner:", a[0, 0], "inboard:", a[h // 2, w // 10], a[h // 10, w // 2])
   ```

   If the inboard samples differ in kind — the target near-white and yours
   near-black, or vice versa — you set a facecolor the target does not have:
   **fix it and re-render**. This is the cheapest large SSIM win available, and it
   is one that eyeballing a dense scatter reliably gets wrong: a black canvas can
   *look* like the shadowed gaps between markers in a crowded panel.

   **Canvas shape is a blind spot in the metrics — measure it yourself.** Every
   similarity signal in `compare_figures.py` resizes both images to a square
   first, so a portrait target reproduced as a landscape figure scores exactly the
   same as one with the right proportions. Nothing will tell you; check it:

   ```python
   from PIL import Image
   for p in (target_path, repro_path):
       w, h = Image.open(p).size
       print(p, f"{w}x{h}", "aspect w/h = %.3f" % (w / h))
   ```

   If the two ratios differ by more than ~10%, set `figsize` to the target's
   proportions (and `ax.set_aspect("equal")` for spatial panels, so the tissue is
   not stretched) and re-render. A figure of the right shape also crops and
   composes like the target, which improves every other signal at once.
