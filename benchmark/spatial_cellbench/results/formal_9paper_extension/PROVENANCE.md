# Nine-paper extension: provenance and reproduction

This directory is the complete scored record of the nine-paper Spatial CellBench extension:
9 papers x 3 arms x 3 replicates = 81 generation units and 81 judge units (729 candidate-level
`gpt-4o` judge calls), all successful. Results tables are in
[docs/spatial_cellbench_results.md](../../../../docs/spatial_cellbench_results.md).

| Arm | Mean paper hit | Pooled hit | Contrast | Estimate | Paired 95% interval |
| --- | ---: | ---: | --- | ---: | ---: |
| Direct | 67.59% | 67.08% | TA - Direct | -2.29 pts | [-10.08, +5.40] |
| TA | 65.30% | 65.02% | TA+CV - TA | +14.41 pts | [+5.74, +21.86] |
| TA+CV | 79.71% | 79.42% | | | |

## Contents

| Path | Content |
| --- | --- |
| `aggregate.json` | Official `run merge` output over the nine paper runs. |
| `papers/<eval_id>/run_meta.json` | Frozen run identity, git state at creation, and every invocation. |
| `papers/<eval_id>/aggregate.json` | Per-paper aggregate: scored rows and the full unit ledger with generation traces. |
| `papers/<eval_id>/generation/<eval_id>/replicate_0R/<arm>.json` | Sealed generation checkpoint: the N proposals, trace, and hashes. |
| `papers/<eval_id>/judging/<eval_id>/replicate_0R/<arm>.json` | Sealed judge checkpoint: per-candidate match decisions with reasons, metrics, and trace. |
| `papers/<eval_id>/judging/<eval_id>/replicate_01/failed/*.json` | Archived failed judge attempts; not scored (see Incidents). |
| `environment_pip_freeze.txt` | `pip freeze` of the Conda environment that ran generation, judging, and merge. |
| `SHA256SUMS` | sha256 of every file here except this document and `SHA256SUMS`. |

Not committed: per-unit TissueAgent workspaces (`work/`, about 1.1 MB per paper), numba and
matplotlib caches (`cache/`), and the Slurm `.out` and local judge log files, which are empty. They
remain on `oven.compbio.cs.cmu.edu` under
`/home/mingqiam/TissueAgent/benchmark/spatial_cellbench/runs/formal_9paper_extension/`.

## Papers

Source DOIs, PMCIDs, and code links are in `data/source_records/`; titles, redaction terms, and
page counts are in `data/corpus_manifest.json`. Scope adjudication dropped no analysis.

| eval_id | Source paper | Analyses |
| --- | --- | ---: |
| `spcb_9f3a1c7d20` | `2023_NC_GraphST` | 10 |
| `spcb_a10b2c3d4e` | `2022_NC_STAGATE` | 9 |
| `spcb_b20c3d4e5f` | `2022_NC_SOTIP` | 10 |
| `spcb_c30d4e5f6a` | `2022_NC_SpaceFlow` | 9 |
| `spcb_d40e5f6a7b` | `2022_NC_SpotClean` | 8 |
| `spcb_e50f6a7b8c` | `2022_NM_Squidpy` | 8 |
| `spcb_f60a7b8c9d` | `2024_GM_SEDR` | 8 |
| `spcb_07b8c9d0e1` | `2023_NC_stLearn` | 10 |
| `spcb_18c9d0e1f2` | `2021_GR_MERINGUE` | 9 |

The nine were chosen from open-access spatial-omics method papers with stable full-text PDFs and
clearly separable spatial-core analyses. MERINGUE replaced SpaGCN because the SpaGCN publisher PDF
endpoint returned an access page; the MERINGUE PDF came from the NSF public-access repository.
BayesSpace, Tangram, CellTrek, and SpiceMix were screened and kept as backups.

The PDFs are in `papers-20260902T-extension-001.zip` (75,152,741 bytes, 28 members, sha256
`7e4e471447ccf88cde5ea1f26ccce584b44e926b240c27466ef411f3a0ec5228`), which is not tracked in git. A
copy is at `oven.compbio.cs.cmu.edu:/home/mingqiam/TissueAgent/`, but that home directory is not
group-readable, so ask Mingqiam for it. Generation and judging read only the frozen JSON under
`data/`; the archive is needed only for `validate_data --archive` and the optional archive branch of
`tests/test_spatial_cellbench.py`. PDFs re-downloaded from the DOIs may not match the recorded hash.

## Frozen identity

Every `papers/<eval_id>/run_meta.json` records the same identity:

| Field | Value |
| --- | --- |
| Protocol | `spatial_cellbench_dynamic_n_v2` |
| Generation model | `o3-mini`, reasoning effort `medium` |
| Orchestration model | `gpt-5.1`, reasoning effort `high` |
| Judge model | `gpt-4o` |
| Arms, replicates | `direct`, `tissueagent`, `tissueagent_spatial_cv`; 3 |
| Source fingerprint | `4e6f997fb26d818935a9e2cc2900bcbbca997b92f766cbe663d9915c6f509c5a` (230 files) |
| `spatial_analysis_overview.md` | `34954dad7d5535ecad3d92e88d9cdc2a2fa9c90b5e3c7f8cad7ed4402a75114e` |
| `public_contexts.json` | `bc714bfccd97f1b1e2d1dd2ec7d41b74dee93e9da5d9587e2514ca78874d6069` |
| `ground_truth.json` | `c0d31c7df5808c89109954d415d9952c8e127f5b890583101ee46859d635380d` |
| `scope_adjudication.json` | `757abc5da8b9485af4572bc21d124d24db2e67f8c4c6cdfb7bd5aec550b34c47` |

## Code state

- The run started on commit `d29e1e8` with uncommitted changes (`run_meta.git.dirty = true`,
  `status_sha256 = 650bf89282db089b8be42cbf3f526eb0badaffa1fd5414ee0d644e0762c81df8`).
- Commit `4716b5375d6abdd22f587d75a9f1679f7840a07b` contains exactly those changes and is
  fingerprint-identical to the run. Its `benchmark/spatial_cellbench/README.md` is the version that
  existed during the run. It was recovered by reversing the post-run README patch (2026-09-03 22:09
  UTC) recorded in the Codex session log, and a clean `git archive` of `4716b53` plus the CellVoyager
  submodule reproduces `4e6f997f...`.
- The source fingerprint hashes `benchmark/spatial_cellbench/*.py`, `*.md`, and `prompts/*.md`;
  `pyproject.toml`; `uv.lock`; selected `src/` and `knowledge/` files; and every `*.py`, `*.txt`, and
  `*.md` under `src/graph/` and `src/agents/`, including submodule checkouts. Later commits edit the
  README, so resume, re-judge, and re-merge this run only from `4716b53`.
- Submodules: CellVoyager (`src/agents/agent_registry/cellvoyager_agent/upstream`) was checked out
  clean at `982a5c241b2b8924495a365b4f640c2b9598f6d3`. The GeneAgent, GeneGPT, and mLLMCelltype
  submodules were not initialized; initializing them changes the fingerprint.
- The launcher's merge-stage loop was edited after the generation array was submitted. Slurm
  snapshots batch scripts at submission, and the edit affects only the merge stage.

## Environment

- Host `oven.compbio.cs.cmu.edu`, Linux x86_64 (glibc 2.28), Python 3.12.13, Conda environment
  `tissueagent` (`environment.yml`) with this repository installed in editable mode.
- Key packages: `openai 1.109.1`, `langchain-openai 0.3.10`, `langchain-core 0.3.64`,
  `langgraph 0.3.20`, `pydantic 2.10.6`, `numpy 2.2.6`, `scanpy 1.10.3`, `squidpy 1.6.2`,
  `anndata 0.12.14`, `python-dotenv 1.2.2`. The full list is in `environment_pip_freeze.txt`.
- Credentials: `OPENAI_API_KEY` from the environment or a repository-root `.env`.
- The `tissueagent` environment has no `pytest`; the tests ran with the base Conda Python.

## Timeline and exact commands

Times are UTC (EDT = UTC-4). All commands ran from `/home/mingqiam/TissueAgent`.

1. 2026-09-02 23:58 UTC: generation array `69838` submitted.

   ```bash
   PAPER_SET=extension \
   RUN_ROOT=/home/mingqiam/TissueAgent/benchmark/spatial_cellbench/runs/formal_9paper_extension \
     sbatch --parsable --array=0-8%3 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh generation
   ```

   Each task ran on the `cpu` partition with 4 CPUs and 24 GB:

   ```bash
   PYTHONPATH="$ROOT/src:$ROOT" PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMBA_NUM_THREADS=2 \
     "$PYTHON" -m benchmark.spatial_cellbench.run run \
       --run-dir "$RUN_ROOT/papers/$PAPER_ID" --paper-id "$PAPER_ID" --replicates 3 \
       --model o3-mini --orchestration-model gpt-5.1 --judge-model gpt-4o --timeout 7200 --skip-judge
   ```

   All nine tasks completed between 2026-09-02 23:58 and 2026-09-03 04:36 UTC, taking 52 to 82
   minutes each, with 81/81 generation units successful.
2. 2026-09-03 15:33 UTC: judge array `70128` (`--array=0-8%3 ... judge`) and dependent merge `70129`
   submitted. Both stayed pending on priority and were cancelled at 19:59 UTC so judging could run
   directly on the host.
3. 2026-09-03 20:15 to 20:39 UTC: local judge attempts, first three papers at a time and then
   serially. They logged rate-limit retry warnings and failed inside a sandbox without network
   access; see Incidents.
4. 2026-09-03 20:52 to 21:18 UTC: the successful serial local judge. It reused every generation
   checkpoint and retried the failed judge attempts.

   ```bash
   ROOT=/home/mingqiam/TissueAgent
   PYTHON=/home/mingqiam/miniconda3/envs/tissueagent/bin/python
   RUN_ROOT=$ROOT/benchmark/spatial_cellbench/runs/formal_9paper_extension
   export PYTHONPATH="$ROOT/src:$ROOT" PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMBA_NUM_THREADS=2
   for paper in spcb_9f3a1c7d20 spcb_a10b2c3d4e spcb_b20c3d4e5f spcb_c30d4e5f6a spcb_d40e5f6a7b \
                spcb_e50f6a7b8c spcb_f60a7b8c9d spcb_07b8c9d0e1 spcb_18c9d0e1f2; do
     "$PYTHON" -m benchmark.spatial_cellbench.run run \
       --run-dir "$RUN_ROOT/papers/$paper" --paper-id "$paper" --replicates 3 \
       --model o3-mini --orchestration-model gpt-5.1 --judge-model gpt-4o --timeout 7200 --retry-failed
   done
   ```

   81/81 judge units succeeded. Each paper's `run_meta.json` lists these invocations.
5. 2026-09-14: from the fingerprint-identical tree, the nine paper runs were merged, the result
   files were copied here, and `results/combined_20paper_aggregate.json` was built.

   ```bash
   "$PYTHON" -m benchmark.spatial_cellbench.run merge --run-root "$RUN_ROOT" \
     --paper-id spcb_9f3a1c7d20 --paper-id spcb_a10b2c3d4e --paper-id spcb_b20c3d4e5f \
     --paper-id spcb_c30d4e5f6a --paper-id spcb_d40e5f6a7b --paper-id spcb_e50f6a7b8c \
     --paper-id spcb_f60a7b8c9d --paper-id spcb_07b8c9d0e1 --paper-id spcb_18c9d0e1f2
   ```

## Incidents

- The early local attempts, first three papers at a time and then serially, logged rate-limit
  retry warnings and ran inside a sandbox without network access. Ten judge attempts failed with
  `APIConnectionError`, all in replicate 1 of GraphST, STAGATE, and SOTIP. They remain under
  `judging/<eval_id>/replicate_01/failed/`. A later `--retry-failed` pass judged every one of those
  units successfully. Only successful judge checkpoints are scored, and `run merge` refuses any
  paper with a failed or missing unit.
- No generation unit failed or was rerun; each paper has exactly one generation invocation.

## Hashes

| Artifact | Hash |
| --- | --- |
| `aggregate.json` file sha256 | `294ce3fe5e295b0693b2a385e48c86862df4fa57206987d8356747dc23d29dee` |
| `aggregate.json` `checkpoint_sha256` | `9958d7a41ca57658303ad931e66fcb40113b7496fdf17e2eb6ef8cc9a97fe571` |
| `../combined_20paper_aggregate.json` `checkpoint_sha256` | `b367c5ee3dcb634155766d7bdd6aed9d3e3e5e97edd8f87dce4594a435a04ed5` |

## Verify without API calls

1. File integrity:

   ```bash
   cd benchmark/spatial_cellbench/results/formal_9paper_extension && sha256sum -c SHA256SUMS
   ```

2. Code identity. Check out the run tree, initialize only the CellVoyager submodule, and confirm
   the fingerprint:

   ```bash
   git worktree add ../ta-ext9-run 4716b5375d6abdd22f587d75a9f1679f7840a07b
   cd ../ta-ext9-run
   git submodule update --init src/agents/agent_registry/cellvoyager_agent/upstream
   PYTHONPATH=src:. python -m benchmark.spatial_cellbench.run run \
     --run-dir /tmp/spcb-check --paper-id spcb_9f3a1c7d20 --validate-only
   ```

   `source_fingerprint` must be `4e6f997f...` with `file_count` 230. Do not add top-level `*.md` or
   `*.py` files to `benchmark/spatial_cellbench/` in that worktree.
3. Deterministic re-merge. From that worktree, merge copies of the committed checkpoints:

   ```bash
   mkdir -p /tmp/spcb-merge
   cp -r <branch checkout>/benchmark/spatial_cellbench/results/formal_9paper_extension/papers /tmp/spcb-merge/
   PYTHONPATH=src:. python -m benchmark.spatial_cellbench.run merge --run-root /tmp/spcb-merge \
     --paper-id spcb_9f3a1c7d20 --paper-id spcb_a10b2c3d4e --paper-id spcb_b20c3d4e5f \
     --paper-id spcb_c30d4e5f6a --paper-id spcb_d40e5f6a7b --paper-id spcb_e50f6a7b8c \
     --paper-id spcb_f60a7b8c9d --paper-id spcb_07b8c9d0e1 --paper-id spcb_18c9d0e1f2
   sha256sum /tmp/spcb-merge/aggregate.json
   ```

   The file must hash to `294ce3fe...`. The bootstrap is seeded, so the output is byte-identical;
   this was checked on 2026-09-14.

## Re-run with API calls

LLM sampling is not deterministic, so reruns are expected to land within the reported
uncertainty, not to reproduce identical hit fractions. Run every command from the `4716b53`
worktree with `OPENAI_API_KEY` set.

- Re-judge only: copy `papers/` into a new run root, delete each paper's `judging/` directory and
  `aggregate.json`, run the step 4 loop with that `RUN_ROOT`, then merge. The generation
  checkpoints are reused. Judge one paper at a time to stay under `gpt-4o` rate limits.
- Full rerun on Slurm into a fresh run root; set `PYTHON` if your environment path differs:

  ```bash
  export PAPER_SET=extension RUN_ROOT=$PWD/benchmark/spatial_cellbench/runs/ext9_rerun
  GEN_JOB=$(sbatch --parsable --array=0-8%3 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh generation)
  JUDGE_JOB=$(sbatch --parsable --dependency=afterok:${GEN_JOB} --array=0-8%1 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh judge)
  sbatch --dependency=afterok:${JUDGE_JOB} --array=0 benchmark/spatial_cellbench/slurm/run_spatial_benchmark.sh merge
  ```
