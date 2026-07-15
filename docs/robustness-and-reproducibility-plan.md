# Implementation Plan: Robustness & Reproducibility

Four independent changes, ordered by value-per-effort. Each ships alone; none
depends on another. Do them in order, but stop anywhere.

| # | Change | Effort | Fixes |
|---|--------|--------|-------|
| 1 | Retry 5xx / timeout / connection errors | ~30 min | Runs dying on transient API blips |
| 2 | Offload truncated tool output to disk | ~2 h | Permanently destroyed tool results |
| 3 | Emit `analysis.ipynb` | ~3 h | No reproducible record of executed code |
| 4 | Durable checkpointing (`SqliteSaver`) | ~4 h + design | All work lost on crash/restart |

Verification for each is behavioural, not just unit tests — see each section.

---

## 1. Retry transient API failures

**File:** `src/server/rate_limit.py:33`

### Problem

```python
RETRIABLE = (openai.RateLimitError, anthropic.RateLimitError)
```

Only 429s retry. `InternalServerError` (500, and Anthropic **529 overloaded**),
`APIConnectionError`, and `APITimeoutError` propagate out of
`agent_model.invoke` (`src/graph/node_factories.py:99`), unwind the graph, and
surface as a generic `run_error` (`src/server/chat.py:676-682`). A 40-minute
analysis dies on a blip the existing backoff machinery would otherwise absorb.

### The wrinkle (why this is not purely a one-line change)

`_compute_wait` (`rate_limit.py:79-94`) trusts a `retry-after` hint whenever one
is present, else falls back to exponential backoff. That logic was written for
429s, where a hint almost always exists. The new error classes mostly arrive
with **no hint**:

- `APITimeoutError` has no `.response` at all → `_extract_retry_after` returns
  `None` via `getattr(exc, "response", None)` → backoff path. Correct already.
- `InternalServerError` / 529 may carry `retry-after`; usually doesn't.
- `APIConnectionError` has no response.

So the backoff path becomes the *common* path rather than the fallback. Current
constants (`_BACKOFF_BASE_SEC = 4.0`, doubling, `_BACKOFF_MAX_SEC = 60.0`) give
4s → 8s → 16s → 32s → 60s across 6 attempts ≈ 2 min of retrying. That is
reasonable for overload; keep it. **Decision: reuse the existing backoff
unchanged.** No new constants.

### Change

```python
RETRIABLE = (
    # 429 — rate limited. Provider usually sends a retry-after hint.
    openai.RateLimitError,
    anthropic.RateLimitError,
    # 5xx — transient server-side. Anthropic 529 (overloaded) is routine and
    # is the single most common cause of a long run dying mid-analysis.
    openai.InternalServerError,
    anthropic.InternalServerError,
    # Network-level. No retry-after hint; _compute_wait falls back to backoff.
    openai.APIConnectionError,
    anthropic.APIConnectionError,
    openai.APITimeoutError,
    anthropic.APITimeoutError,
)
```

### Explicitly NOT retriable

Do not add these — they are deterministic and retrying burns quota to fail again:
`BadRequestError` (400), `AuthenticationError` (401), `PermissionDeniedError`
(403), `NotFoundError` (404), `UnprocessableEntityError` (422).

`APIStatusError` is the **base class** of several of the above — do not add it,
it would swallow 400s.

### Risk

A genuinely-down provider now takes ~2 min to surface an error instead of
failing fast. Acceptable: the alternative is losing the run. Note
`max_attempts=6` is shared with 429s (`src/server/main.py:63-69`); no change.

### Verify

1. Unit tests (`tests/test_rate_limit.py`, new — this module is pure logic and
   currently untested):
   - `InternalServerError` retries then succeeds on attempt 2.
   - `BadRequestError` raises immediately, zero sleeps.
   - `APITimeoutError` (no `.response`) → uses backoff, does not crash in
     `_extract_retry_after`.
   - `retry-after-ms` header honoured; exhaustion re-raises the original.
   - Patch `time.sleep`/`asyncio.sleep` so tests stay fast.
2. Constructing these exceptions requires `response=`/`body=` kwargs — build
   them with a dummy `httpx.Response` and assert the constructor signature
   matches the installed SDK versions (`openai>=1.73.0`, `anthropic==0.52.0`).
   **If a class doesn't exist under that name, this test fails loudly rather
   than silently never matching.**

---

## 2. Offload truncated tool output instead of destroying it

**Files:** `src/agents/agent_utils.py:147`, new
`src/agents/output_spill.py`, callers in `src/agents/agent_tools.py:99,142,180`
and `src/agents/agent_registry/coding_agent/sandbox.py:428`

### Problem

```python
def truncate_output(text: str, max_chars: int) -> str:
    half = max_chars // 2
    removed = len(text) - max_chars
    return f"{text[:half]}\n\n... [{removed} characters truncated] ...\n\n{text[-half:]}"
```

Middle-out truncation at `MAX_OUTPUT_CHARS = 3000` (`src/config.py:130`). The
removed middle is **gone** — no path, no handle, no recovery. An agent printing
a large DataFrame loses the middle rows permanently.

### Design

Mirror `coding_agent/image_spill.py` exactly — it already solves this shape for
plot images (write to `outputs/.../_trace/`, return a project-relative path,
never raise). Reuse its conventions:

- Write full text to `outputs/_trace/output/<uuid>.txt` under
  `ACTIVE_PROJECT_DIR`. Under `outputs/` so it travels with the project on
  park/promote and survives `reset_data_directories` (per `image_spill.py:21-24`).
- Return a project-relative path — the same form `read` accepts.
- **Never raise.** A spill failure must degrade to today's behaviour (plain
  truncation), exactly as `spill_images_to_disk` skips-and-logs.

New `src/agents/output_spill.py`:

```python
def spill_text_to_disk(text: str) -> str | None:
    """Write full text under outputs/_trace/output/; return project-relative
    path, or None on any failure (caller falls back to plain truncation)."""
```

Then `truncate_output` gains an **opt-in** parameter:

```python
def truncate_output(text: str, max_chars: int, *, spill: bool = False) -> str:
```

When `spill=True` and truncation occurs, attempt the spill and put the path in
the notice:

```
... [12481 characters truncated — full output: outputs/_trace/output/ab12.txt
     (use read with this path, offset/limit to page through)] ...
```

If the spill returns `None`, emit today's notice verbatim.

### Why opt-in rather than default-on

`truncate_output` has callers that must **not** spill:
`src/graph/graph.py:184,192` truncate a prompt preview to 600 chars for display.
Spilling those would write junk files on every graph build. Default `False`
keeps every existing caller byte-identical; only the four data-bearing sites
opt in.

### Call sites to change (add `spill=True`)

| File:line | Tool | Note |
|---|---|---|
| `agent_tools.py:99` | `glob` | |
| `agent_tools.py:142` | `grep` | |
| `agent_tools.py:180` | `read` | Already supports `offset`/`limit`; spill gives the agent a path to page |
| `sandbox.py:428` | kernel output | Highest value — this is where analysis results die |

Leave `graph.py:184,192` untouched.

### Prompt update

The agent must know the path is readable. Add to
`coding_agent_prompt.txt` and `coding_agent_prompt_no_sandbox.txt`: when output
is truncated with a `full output:` path, `read` that path with `offset`/`limit`
to inspect the middle rather than re-running the cell.

### Housekeeping

`_trace/output/` grows unboundedly. `outputs/figures/_trace/` already has this
property and is apparently tolerated — match it for now, note as follow-up.
Do **not** add a cleaner in this change.

### Verify

1. Unit: text under limit → unchanged, no file written. Over limit + `spill=True`
   → file exists, contains **full** text, path appears in notice. Spill failure
   (patch to raise) → falls back to old notice, no exception.
2. Behavioural: run a cell printing ~50k chars; confirm the notice carries a
   path and that `read` on it returns the middle content.
3. Regression: `graph.py` prompt previews write no files.

---

## 3. Emit a reproducible `analysis.ipynb`

**Files:** new `src/agents/agent_registry/coding_agent/notebook_log.py`, hooks in
`coding_agent/model.py:147-155` (`python`) and `:167-175` (`r`)

### Problem

No executable record of the agent's analysis exists. Executed code lives only in:
1. `.chat.json` — prose+code interleaved, not runnable, and a *dotfile inside
   the project dir* (easy to miss when sharing results)
2. `logs/` — 702 rotating files, uncorrelated with project IDs
3. The kernel's `In[]` history (`sandbox.py:289`) — dies with the kernel

A collaborator receives `outputs/figures/umap.png` and cannot re-derive it.

### Dependency: confirmed available

`nbformat>=5.10.4` is already a declared dependency in `pyproject.toml` and
resolves in `.venv` (5.10.4). No new dependency.
(Note: it does **not** import under the ambient conda python — build/run this
against `.venv`.)

### Design

Both `python()` and `r()` funnel through one place each, immediately after
`kernel_client.execute(...)` returns — the same interception point where
`_emit_output` already sits. Append there.

```python
# notebook_log.py
def append_cell(code: str, result, language: str) -> None:
    """Append an executed cell + its outputs to outputs/analysis.ipynb.
    Never raises — logging must not break code execution."""
```

Details:

- **Path:** `ACTIVE_PROJECT_DIR / "outputs" / "analysis.ipynb"` — a normal
  visible artifact next to the figures, not a dotfile.
- **Read-modify-write** the notebook per cell. Simple, crash-safe (each cell is
  durable the moment it runs), and correct even if the server dies mid-run.
  At a few hundred cells the rewrite cost is negligible against a kernel call.
  Write to a temp file + `os.replace` for atomicity.
- **R cells:** a `.ipynb` has one kernelspec. Since Python dominates, set the
  kernelspec to Python and record R cells as `%%R`-prefixed code cells with a
  comment noting they ran in the IRkernel. Honest and readable; a pure-R project
  is a follow-up (emit `analysis-r.ipynb` separately).
- **Outputs:** record stdout as `stream` output and images as `display_data`
  with base64 — so the notebook renders plots standalone. Note this duplicates
  bytes already in `outputs/figures/_trace/`; accept it, the notebook must be
  self-contained to be shareable.
- **Never raise.** Wrap the whole call in try/except and log. Same discipline as
  `image_spill.py:41-43`.
- **Reset:** the notebook is per-project. New project → new notebook. Since it
  lives under `ACTIVE_PROJECT_DIR`, project switching handles this for free —
  verify against `set_kernel_workspace` (`src/server/main.py:118-132`).

### Environment capture

The notebook's first cell should be a provenance header written on creation:
timestamp, model IDs, and package versions for the scientific stack (scanpy,
squidpy, anndata, numpy, pandas). Without it, the same notebook produces
different numbers on a different scanpy version — the exact failure this change
exists to prevent.

Capture versions **by executing a cell in the kernel**, not by importing in the
server process — the kernel is where the analysis actually runs, and its env
differs from the server's (Docker sandbox, or `/opt/venv`).

Dataset hashes and random seeds: out of scope here, note as follow-up.

### Deliberately NOT doing

- Not re-executing the notebook to verify it reproduces (nbclient) — expensive,
  and a follow-up once the artifact exists.
- Not stripping failed cells. A cell that errored is part of the record; keep it
  with its traceback.

### Verify

1. Behavioural, and this is the real test: run a short multi-step analysis, then
   **open `outputs/analysis.ipynb` in Jupyter and run it top-to-bottom.** It
   should reproduce the figures. This is the only check that matters.
2. Cell count matches the number of `python`/`r` calls; failed cells appear with
   tracebacks; plots render inline.
3. Fault injection: patch `append_cell` to raise → code execution still succeeds.
4. Project switch mid-session → second project gets its own notebook, first is
   untouched.

---

## 4. Durable checkpointing

**File:** `src/server/main.py:96`

### Problem

```python
session.agent = graph.compile(checkpointer=MemorySaver())
```

In-process RAM. A run that dies at step 4/5 restarts from the planner.

### Why this is worth more than it looks

The Jupyter kernel is a **separate process** (`LocalKernelGateway` / Docker), so
`adata` and every loaded object **survive a server restart**. The agent just has
no memory that they did. Durable checkpoints + a live kernel means genuinely
resuming mid-analysis rather than recomputing — the expensive state is already
intact.

### Why it is not a one-line swap

`thread_id` is regenerated per user turn (`src/server/session_manager.py:22-24,56`)
and cycled on resume-with-feedback (`src/server/chat.py:854`), deliberately
orphaning checkpoints. `MemorySaver` is currently described in-code as
"effectively no-op overhead for autopilot runs" (`main.py:82-84`). Resume
requires deciding **what a resumable unit is** — that is a design question, not
a code change:

- Which `thread_id` does a crashed run resume from?
- Does a resumed run re-dispatch the in-flight step, or trust its artifacts?
- How does resume interact with `gates_fired` (`session_manager.py:68`) so
  copilot gates don't re-fire or wrongly skip?

Sub-agent graphs compile with **no checkpointer** (`graph.py:129`,
`coding_agent/model.py:220`) — mid-step crashes lose that step regardless.
`tests/test_subagent_checkpoint_safety.py:41` exists because sub-graph state has
already caused msgpack serialization failures in the parent checkpointer; adding
a real serializing backend **will re-open that hazard**. Read that test first.

### Staging

1. **Swap `MemorySaver` → `SqliteSaver`** (`langgraph-checkpoint-sqlite`, new
   dep). Change nothing else. Verify existing behaviour is byte-identical —
   copilot gates, autopilot, `tests/test_resume_protocol.py`,
   `tests/test_interrupt_mechanics.py`, and especially
   `test_subagent_checkpoint_safety.py` all still pass. Ship this alone.
2. **Then** design resume-after-crash as a separate piece of work, informed by
   what stage 1 reveals about serialization.

Do not attempt both at once.

### Verify

- Full existing suite (44 tests, 6 files) green — `test_resume_protocol.py` and
  `test_interrupt_mechanics.py` are the contract here.
- Behavioural: copilot run pauses at both gates, approve/edit/feedback still work.
- A checkpoint DB file appears and is non-empty after a run.
- Fault injection: kill the server mid-run; confirm the DB holds the last
  checkpoint (proving durability, without yet wiring resume).

---

## Sequencing

1 and 2 are independent — either can go first. 3 benefits from 2 being in place
(truncated cell output is what gets logged), but doesn't require it. 4 is last
and gated on stage 1 passing cleanly.

**Suggested first PR:** #1 + its tests. Small, self-contained, fixes the most
common cause of lost runs, and adds the first test for a module that had none.

## Out of scope (noted, not planned)

- Real cancellation via subprocess isolation (`chat.py:580-589` — Stop currently
  abandons the run; the orphan keeps burning tokens and blocks the next run on a
  1-worker pool). Structural.
- Context-size backstop at `node_factories.py:94-99`.
- Cache-token tracking + prompt reordering (`usage_tracker.py:60-62` reads only
  `input_tokens`/`output_tokens`, so caching benefit is currently unmeasurable).
- `_trace/` cleanup policy.
