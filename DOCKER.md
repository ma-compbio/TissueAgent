# Coding sandbox

The cached coding agent (`src/agents/agent_registry/coding_agent_cache/`) can execute code either directly on your host or inside an isolated Docker container. Select it with `TISSUEAGENT_CODING_AGENT=cache`. The canonical DeepAgent implementation uses local shell execution and does not use this sandbox. The container-based mode is toggled from the web UI's **Settings** page. Both cached modes speak the same Jupyter Kernel Gateway protocol, so their behavior is identical — only the execution environment changes.

## What it is

An Ubuntu-based image (built from [`docker/Dockerfile`](docker/Dockerfile)) that runs a Jupyter Kernel Gateway inside a container named `tissueagent-sandbox`. The image ships two ready-to-use kernels:

- **Python 3.13** — pre-installed with the spatial-transcriptomics core (`scanpy`, `squidpy`, `anndata`, `liana`, `decoupler`, `matplotlib`, `plotnine`, …) and the CCC ensemble stack (`commot`, `stlearn`, `pycirclize`, `upsetplot`).
- **R** (via `IRkernel`) — enabling Seurat / Bioconductor workflows without needing R on the host.

Two named Docker volumes persist across container restarts:

| Volume | Container path | Purpose |
| --- | --- | --- |
| `tissueagent-pyenv` | `/opt/venv` | Python venv — new `pip install`s survive restarts |
| `tissueagent-rlibs` | `/opt/R/library` | R library — new `install.packages()` survive restarts |

The host `workspace/` directory is bind-mounted at `/workspace`, so files the agent reads or writes are visible on the host at the same paths documented in the main README's *Runtime data layout* section.

## What you gain

- **Isolation from the host.** The container runs with `cap_drop=ALL` and `no-new-privileges`; the only writable path outside the venv/R volumes is the bind-mounted workspace. LLM-generated code can't touch `/home`, `/etc`, or anything else on your machine.
- **Reproducible environment.** Every user runs identical package versions regardless of host OS or Python setup. Bug reports become actionable.
- **Batteries-included scientific stack.** The CCC ensemble (LIANA+ / COMMOT / stLearn), a working R kernel, and the core scanpy/squidpy/anndata trio are all pre-installed. No per-project environment fiddling.
- **Clean rollback.** If a package install breaks things, `docker volume rm tissueagent-pyenv` resets the Python side to the image's baseline without touching your host.

## What you give up

- **Docker must be running.** Requires Docker Desktop (macOS / Windows) or a running `dockerd` (Linux). If Docker is unavailable, either disable the sandbox in Settings or start a local Jupyter Kernel Gateway on `127.0.0.1:8888` — the agent uses whichever it finds.
- **Cold-start cost.** The first enable builds the image from scratch (~5–15 min depending on network) and downloads several GB of dependencies — `stlearn` pulls the full PyTorch + CUDA runtime.
- **Disk footprint.** Once populated, the image + volumes typically occupy **8–12 GB**.
- **Host-installed Python packages are invisible to the sandbox.** If you `pip install` something into your `.venv` for local iteration, the agent won't see it unless you also install it inside the container (see below).
- **Small per-execution overhead.** Each code call is a websocket round-trip to the container. Negligible for typical analysis code (seconds-to-minutes) but not free.

## Usage

**Enable / disable.** Web UI sidebar → **Settings** → **Docker sandbox**. Toggling on will build the image if needed and start the container. Toggling off stops the container but preserves the volumes for next time.

**First-run notes.** The initial build streams progress to the backend log (`logs/*_tissueagent.log`). If the build fails, resolve the error, delete the partial image with `docker rmi tissueagent-sandbox`, and re-enable from the UI.

**Install extra packages at runtime.** Two options — both persist in the named volumes:

```bash
# Python
docker exec tissueagent-sandbox pip install <package>

# R
docker exec tissueagent-sandbox Rscript -e 'install.packages("<package>", repos="https://cloud.r-project.org")'
```

You can also install from inside a running agent via a `python()` cell (`import subprocess; subprocess.run(["pip", "install", "<pkg>"])`), but restart the kernel afterwards so the new package is picked up.

**Force a clean rebuild.** Useful after editing `docker/Dockerfile`:

```bash
docker stop tissueagent-sandbox && docker rm tissueagent-sandbox
docker rmi tissueagent-sandbox                            # rebuilds image on next enable
docker volume rm tissueagent-pyenv tissueagent-rlibs      # optional: also wipes package state
```

Docker will not overwrite an existing non-empty volume from the image, so removing the volumes is required if you want a Dockerfile change to actually reach the runtime environment.

**Ports and paths.** The kernel gateway listens on `127.0.0.1:8888` inside the sandbox (see `src/config.py:115` if you need to change it). The container's working directory is `/workspace`, bind-mounted from `workspace/` on the host.
