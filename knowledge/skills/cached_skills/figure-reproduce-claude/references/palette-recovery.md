# Palette recovery — getting the target's colours, whatever kind of figure it is

Colour is the single highest-leverage thing to get right, and the one the structural
metrics are blindest to: SSIM is computed on grayscale, so a reproduction in entirely
the wrong palette can score 0.99 and still be wrong. This page is the decision tree for
recovering the target's actual colours, and — just as important — for knowing when you
have **not** recovered them and must say so.

The governing rule, from the skill's invariants: **never silently substitute a default
palette.** A named colour (`"blue"`, `"tab:blue"`, `C0`) or an unexamined `cmap` in the
plotting code means the palette was invented, not measured.

---

## 1. Where does the colour live?

Ask this before running anything. It selects the tool; guessing wrong here wastes
attempts and, worse, can produce a confident wrong answer.

| The panel… | Colour lives in | Use |
|---|---|---|
| has a legend with keyed swatches | the legend | `extract_reference_spec.py --legend-box` → tier 3 |
| colours its **marks** by category and names them on the tick axis (bar, violin, box, strip, dotplot) | the marks | `--marks-box` → **tier 4** |
| has a colorbar (continuous values) | the colorbar ramp | `--colorbar-box` → a `cmap` name, not a category map |
| ships its own colours with the data | `adata.uns["<key>_colors"]` | tier 2, `build_colormap.py --dataset` |
| came with an authors'/user's palette file | that file | tier 1, `--palette` (wins outright) |

A figure can be more than one of these (a legend *and* a colorbar). Handle each.

---

## 2. The tier ladder

`build_colormap.py` **stamps the tier into the file**, so the plotting code and a later
reader can both check where the colours came from. The tier names below are the strings
the script writes; the *trust order* is the *Prefer* column, which ranks by how directly
a source is evidence about **this figure**:

| Prefer | Tier stamp | Source | How |
|---|---|---|---|
| **1st** | `3-legend` | swatches measured off the reference legend | `--reference FIG [--legend-box …]` |
| **2nd** | `4-marks` | per-category mark colours, legendless panels | `--reference FIG --marks-box …` |
| **3rd** | `1-supplied` | a palette supplied *for this target* | `--palette FILE` |
| **4th** | `2-dataset` | `adata.uns["<key>_colors"]` | `--dataset FILE --key COL` |
| last | `5-default` | a documented fallback | `--allow-default` — records a DEVIATION |

Tier 5 is not a palette, it is an admission. If you reach it, the repro note must say so
plainly; the figure is not a colour match and no amount of polish makes it one.

**Stored metadata is the trap, because it looks like provenance.** An ordered colour list
sitting beside a category column is not a *named binding to this figure* — it is whatever
tool last plotted that object, persisted on save. Measured on a real task,
`adata.uns["<key>_colors"]` was byte-identical to the plotting library's default palette
and sat a **mean RGB distance of 127** from the published figure's colours (0 = identical,
>100 = unrelated): every category wrong, in a source that passes every structural check a
resolver can make — stored by the authors, correctly keyed, correctly ordered, right
length. Only comparison against the panel catches it. Use it when the target shows no
names, and even then spot-check two or three categories against reference pixels (§5).

**A supplied palette file is not automatically the right one either.** "A palette file
exists" and "this palette is the one the target used" are different claims. A file that
disagrees with the panel is well-sourced and wrong; the panel wins.

**If two named sources disagree, stop and report the conflict** rather than silently
picking one — the disagreement is itself the finding.

---

## 3. Legends: measure, then decide whether to believe it

```bash
python scripts/extract_reference_spec.py TARGET -o spec.yaml            # try auto
python scripts/extract_reference_spec.py TARGET --legend-box X0,Y0,X1,Y1 \
       --max-legend-entries 64 -o spec.yaml                             # when auto misses
```

Read **two** fields, not one:

- `legend.status` — did the parser run?
- `legend.confidence` — **should you believe it?** `high` / `low` / `rejected`

These are different questions and conflating them is the classic failure. A parser that
runs cleanly on a panel with no legend at all still returns *something*: on a real
legendless violin figure it returned three 5–7px fragments of violin outline sitting in
the margin, labelled none of them, and reported `ok`. Only `confidence: high` licenses
building a palette from legend entries.

`confidence` is decided from properties every real legend has and stray plot marks do
not: swatches are **big enough to read** (≥6px), **flush in one column**, and on an
**even vertical pitch**. The `evidence` block shows the numbers behind the verdict.

### Reconcile the count before you plot

Even at `high`, compare the entry count against the dataset's category count. They
disagree for three ordinary reasons, and the fix differs:

| Situation | Meaning | Do |
|---|---|---|
| legend has **more** entries | the figure shows classes your dataset lacks | plot the ones you have; name the rest in the repro note |
| legend has **fewer** entries | a swatch went undetected, or the panel drops a class | find it (§4) before pairing positionally |
| counts match | good | still spot-check the first and last pairing |

`build_colormap.py` pairs by **normalised label** when labels are available — case,
punctuation inside compound names, and the British/American `ae`/`e` spelling of the
same term are all folded, so a legend and a dataset that write one category slightly
differently still pair. Prefer this over positional pairing: a single missing swatch
shifts every positional assignment after it, silently.

---

## 4. When the legend is incomplete: pale swatches

Swatch detection rejects near-white and near-grey pixels as background — a fixed global
cut, with no local-contrast model. A cream, pale-yellow or light-grey swatch therefore
disappears, and its category is simply absent from the palette.

The symptom is `confidence: low` with `spacing_cv` elevated: the missing entry leaves a
double-width gap in an otherwise even column. **This is not a reason to reject the
legend** — the other entries are correctly measured. Recover the missing one directly:

```python
from PIL import Image
import numpy as np
img = np.array(Image.open(target).convert("RGB"))
# The gap sits between two detected entries; sample the swatch column at its midpoint.
patch = img[y_mid-4:y_mid+5, x_swatch-4:x_swatch+5].reshape(-1, 3)
d = np.abs(patch.astype(int) - 255).sum(1)          # distance from page white
print(patch[d >= np.percentile(d, 60)].mean(0))     # core, ignoring anti-aliased edge
```

Add it to `colormap.yaml` by hand **and record in the repro note that you did**, with
the pixel coordinates you sampled. A hand-added colour with a stated provenance is
honest; a hand-added colour that silently changes the provenance stamp is not — and
`--verify` will catch the latter.

---

## 5. Legendless categorical panels — tier 4

Bar, violin, box and strip panels routinely have no legend: the categories are named on
the tick axis and distinguished by the mark colours themselves. Tiers 1–3 all miss, and
without tier 4 the run falls through to an invented default palette for a figure whose
colours are sitting right there, fully measurable.

```bash
python scripts/build_colormap.py --reference TARGET \
       --marks-box X0,Y0,X1,Y1 --marks-axis x \
       --dataset data.h5ad --key cell_type -o colormap.yaml
```

`--marks-box` is the **plot area** (the axes interior), not the whole figure. Along the
category axis each mark is a contiguous run of columns separated by background, so the
runs are the categories, in plotting order.

Two cautions, both load-bearing:

- **Order is the pairing.** Mark *i* is category *i* along the axis. If the dataset's
  category order differs from the panel's, the colours land on the wrong names. Check
  the first and last mark against the panel by eye before accepting.
- **Tick labels usually will not OCR.** A many-category axis is nearly always rotated,
  and rotated text defeats OCR — on a real panel it recovered only a couple of junk
  fragments for a full row of marks.
  The tool deliberately **refuses to attach labels when the counts disagree**:
  the colours and their order are good, and a wrong name is worse than no name. Supply
  the names from the dataset in that same order.

---

## 6. Continuous panels

A colorbar is not a category palette — recover a **colormap name and a value range**:

```bash
python scripts/extract_reference_spec.py TARGET --colorbar-box X0,Y0,X1,Y1 -o spec.yaml
```

`colorbar.matches` is best-first by mean dE across the ramp. Take `colorbar.best` and
**mind the `_r`**: `RdBu` and `RdBu_r` are equally plausible matches to a careless read
and invert the figure's meaning. Match `vmin`/`vmax` to the colorbar's tick labels too;
the right colormap over the wrong range still misreads the data.

---

## 7. Before you plot

```bash
python scripts/build_colormap.py --verify colormap.yaml
```

This recomputes the provenance digest over the colours, their order and the tier. It
exists because a hand-written `colormap.yaml` carrying a fake tier header is
indistinguishable, by eye, from a measured one — and passing a default palette off as
measured is the failure this whole page is built to prevent.

Then check, in the plotting code:

- every colour traces to `colormap.yaml` (or a measured `cmap`), never a literal;
- the source tier is recorded in the repro note;
- any hand-added or unrecovered colour is named there explicitly;
- categories are iterated in the target's order, so legend order and z-order match.

## 8. When you genuinely cannot recover it

Say so. An honest note — "the legend swatch for *X* is below the detector's contrast
floor; its colour is approximated" — is worth more than a confident palette that is
quietly wrong. Never tune data or thresholds to make colours line up: that is
over-matching, and it corrupts the figure to flatter the metric.
