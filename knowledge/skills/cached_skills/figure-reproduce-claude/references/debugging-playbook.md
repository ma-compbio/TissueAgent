# Debugging playbook — symptom → cause → fix

Concrete failure modes seen across hundreds of real figure reproductions,
generalized to any data/plotting stack. When a reproduction is off, find the row
whose **symptom** matches and apply the **fix**. Pair this with the
`reflect-and-retry.md` loop (this table tells you *what* to do; that loop bounds
*how many times*).

## A. Code issues

| Symptom | Cause | Fix |
|---|---|---|
| Picked the wrong entry script; "no plotting code" | You judged from the file *tree*, not file *content* | **Read the code.** Grep the repo for calls to plotting libs (`matplotlib`, `plt.`, `ggplot`, `sns.`, `sc.pl`, `plot(`) to find the file that actually draws this panel — not a compute/util module. |
| Wrong language assumed (ran Python for an R repo, or vice-versa) | Guessed language from the figure, not the code | Derive language from the **resolved entry file's extension** (`.R/.Rmd`→R, `.py/.ipynb`→Python). Never coerce; run the author's actual language. |
| `FileNotFoundError` on a path baked into a script | Author hard-coded an absolute/cluster path that doesn't exist here | **Basename-search before giving up:** take the basename (`X.rds` from `/staging/.../X.rds`), `find . -iname 'X.rds'` (then an `X*` glob); if found, symlink/copy it to the expected path and record the substitution. Only declare "missing" after the search is empty. |
| "Code" download is a 60 KB HTML page | A DOI/landing URL was fetched instead of the archive | Resolve the record via its API (Zenodo/Figshare/OSF) or the repo's release/zip; verify you got source files, not `<!DOCTYPE html>`. |
| A notebook won't run headless | Needs a kernel / interactive state | Execute it non-interactively (`jupyter nbconvert --to notebook --execute`), then pick the cell/figure for **this** panel and save it. |
| Multi-figure script emits many images | One script draws the whole paper | Run it, then select the output that corresponds to **this** panel (by title/label) and save that one as the reproduction. |

## B. Data issues

| Symptom | Cause | Fix |
|---|---|---|
| The color column / embedding the figure needs isn't in the data | Figure uses a derived field (clusters, UMAP, annotation) not shipped | Compute it if the data supports it (run the upstream clustering/embedding/annotation first); else reproduce the closest supported variant and **say so**. Never invent the field. |
| Plot shows far more series/rows than the target panel | You plotted the whole sheet | Plot **only the subset** the panel shows — the same rows/series/categories, in the shown order and grouping. Curated "top 10" ≠ the full 40-row sheet. |
| Feature/gene not found | Identifier scheme mismatch (symbol vs Ensembl/Entrez id) | Map identifiers first (build a symbol↔id table); then subset. |
| Values are close but systematically off | **Raw vs processed** data mismatch (log/normalized vs counts) | Apply the transform the Methods/caption imply (log1p, CPM/TPM, z-score, scaling); cache the processed matrix so retries don't recompute. |
| A referenced dataset is absent locally | Data lives in an external deposit (GEO/Zenodo/atlas/URL) not staged | Locate it via the accession in the paper; download small files; for large/gated ones, record the link + why it's blocked and reproduce what you can. |
| Re-running a big prep each attempt | No caching | **Sentinel-gate** expensive steps: `if [ ! -f step.done ]; then <prep>; touch step.done; fi`. |

## C. Environment issues

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError` / package "not found" at runtime although you "installed" it | Verified against a *different* interpreter/library path than the one that runs the code | Install into (and verify against) the **exact** interpreter that executes the plot: `python -c "import pkg"` / `Rscript -e 'library(pkg)'` on the run path. |
| A source build fails (missing system libs, toolchain) | Heavy package compiled from source (e.g. some R/Bioconductor or geospatial libs) | Prefer a prebuilt wheel/conda-forge/binary; install the system deps it names; or pin a version with a prebuilt artifact. Record it as an obstacle if truly unbuildable. |
| Installed the CPU build on a GPU box (or the reverse) | Generic env file, no hardware variant | Match the framework build to the hardware (CUDA build when a GPU is present); verify (`torch.cuda.is_available()`); keep the repo's **pinned** version, don't jump to latest. |
| Network-restricted sandbox blocks installs/downloads | The execution sandbox has no network | Do installs/downloads in a networked step *before* the sandboxed run, or stage files in first; then run the plot offline. |
| The agent wanders into unrelated tools/config | Global CLI/plugin config leaked into the run | Keep the run focused on this panel; ignore unrelated global skills/config. |

## D. Methodology issues

| Symptom | Cause | Fix |
|---|---|---|
| Right pipeline, wrong numbers | **Undocumented preprocessing** (filter thresholds, normalization, batch correction unstated in the main text) | Read the **Methods + supplementary + code comments** for this panel; apply the implied steps. State any assumption in the note. |
| Output differs every run (embedding rotated, clusters relabeled) | **Stochastic** method (UMAP/t-SNE/Leiden/random init) | Set every seed/`random_state`; for heavy models reuse one trained checkpoint across panels. Accept a **qualitative (B3)** match — same structure, not pixel-identical — as success. Don't chase pixels. |
| A faithful reproduction still "looks wrong" vs the target image | **Figure-duplication trap:** you're comparing against the wrong reference (main **Fig. 3** vs **Extended Data Fig. 3** share a number) | Re-acquire the correct target: disambiguate by *kind* (main / extended / supplementary) **and** number before comparing. |
| The paper panel isn't the plot your dataset yields (it's a schematic/photo, or a different representation) | The literal PDF panel isn't derivable from your data; the true reference lives elsewhere | Use the **authors' plotting-code output / the caption's described plot** as the target of record (flag any circular reference if you regenerate it from the repo's own script); if not derivable from the data at all, **honest-failure**. |
| Kept a raw microscopy/schematic panel that can't be "reproduced from data" | Panel isn't an analytical plot | Recognize non-analytical panels (raw imaging, diagrams, photos) and don't try to regenerate them from a data table — say so. |
| Spatial map looks sparse/floating vs the paper | Dropped the background underlay | Keep the tissue/histology image (or the paper's background) as the underlay; don't draw on a plain white canvas. |

## Golden rules

1. **Read the code and the Methods** before deciding what to run — most "mysteries" are documented somewhere in the repo/paper.
2. **Search before you declare missing** (basename search across all roots).
3. **Reproduce the panel, not just the data** — verbatim labels, exact subset, matching visual form.
4. **Set seeds; accept qualitative matches** for stochastic methods.
5. **Never fabricate.** Honest-failure with a named gap beats a faked match.

---

## Quick list (moved from the skill body)

- **Missing field → can't reproduce as-is.** The target colors by a
  column/embedding the dataset lacks. Compute it if the data supports it (run the
  relevant analysis first), or reproduce the closest supported variant and say so.
- **Identifier mismatch.** A figure keyed by gene/feature won't plot if names use a
  different ID scheme — map identifiers first.
- **Category/palette mismatch.** Categories render in a different order or different
  colors than the target. Don't fix this by eye: run
  `scripts/extract_reference_spec.py` and set the category order and color map from
  its YAML. Naming a color from a downsampled image ("looks blue" → `tab:blue`) is
  the single most common source of this error, and grayscale metrics can't see it.
- **Wrong colormap direction.** `RdBu` vs `RdBu_r` is a frequent miss on continuous
  panels and inverts the figure's meaning. Identify it with `--colorbar-box` rather
  than guessing.
- **Paraphrased labels.** Axis/legend/tick text rewritten rather than copied
  (`"expression"` for `"Expression (log2 CPM)"`). The `compare_figures.py` text diff
  flags these as near-misses when OCR is available; otherwise copy them verbatim.
- **Wrong plot primitive.** A "heatmap" in a paper may be a clustermap, matrixplot,
  or dotplot — match the actual encoding.
- **Missing input file.** Before declaring a data/script input missing, **search
  for it by basename** across the mounted roots — authors often hard-code a path
  that ships at a different location. See the playbook.
- **Blank/None image.** On a `python` kernel a missing backend produces no inline
  image — ensure it is reachable. On a shell-only engine figures are *never*
  inline; that is expected, not a failure. Check the file on disk is a valid
  non-empty image and use `scripts/compare_figures.py` to judge it.
- **Over-matching.** Don't tweak data or thresholds just to make the picture look
  identical — reproduce what the data legitimately yields and document differences.

The full symptom → fix taxonomy (code, data, environment, methodology — including
stochastic embeddings and figure-duplication traps): `references/debugging-playbook.md`.
