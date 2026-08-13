# Spec: Per-Run Benchmark Metrics (BioMysteryBench, GPT vs Claude)

What every benchmark run must record, where each field comes from, and what
still needs instrumenting. Scope: the 34-task `BioMysteryBench-Expression`
subset run under two model families.

**Status legend** — ✅ already in state, needs persisting · ⛏ mined from
`full_stdout.log` post-hoc (no code change) · ⚠️ needs new instrumentation · ○
derived at analysis time (never stored).

**Acquisition strategy: dump what state already knows, mine the rest.** Exactly
one code change is required (§8) — a purely additive `metrics.json` dump in
`cli.py`. Everything qualitative comes from trace mining, which needs no code
change and works retroactively on runs already archived. Read §8 before §5: it
explains why naive `grep` of the trace is *provably wrong*.

---

## 1. Unit of record

One **run** = one `(task_id, model, seed)` triple. One run emits exactly one
`metrics.json`. Nothing is aggregated at write time — aggregation is a pure
function of the run corpus, so it can be re-derived without re-running.

```
benchmark/biomysterybench/biomysterybench_expr/runs/
  <model_id>/<task_id>/<seed>/
    metrics.json      # this spec
    full_stdout.log   # already produced (slurm/run_problem.sh:35)
    answer.txt
    outputs/          # archived artifacts
```

**Decision: N = 3 runs per (task, model).** A single run cannot separate model
skill from luck; the all-or-nothing rubrics make per-run scores binary and
therefore high-variance. N=3 gives pass@1 (mean) and pass@3 (any) at 34 × 2 × 3
= 204 runs. See §7 for the cost consequence.

---

## 2. Run identity & configuration

Fixes what was run, so a result is reproducible and attributable.

| Field | Type | Source | Status |
|---|---|---|---|
| `run_id` | str | `<model_id>/<task_id>/<seed>` | ⚠️ |
| `task_id` | str | `problems.csv` | ✅ |
| `bucket` | enum | `manifest.csv` — `annotation`\|`differential-expression`\|`clustering` | ✅ |
| `human_solvable` | bool | `manifest.csv` | ✅ |
| `dataset_bytes` | int | zip size (LFS pointer `size:`) | ✅ |
| `seed` | int | harness | ⚠️ |
| `orchestration_model` | str | `models.get_selection()` | ✅ |
| `worker_model` | str | `models.get_selection()` | ✅ |
| `provider` | enum | `models.py` — `openai`\|`anthropic`\|`openrouter` | ✅ |
| `reasoning_effort` | str\|null | `ModelSpec.reasoning_effort` (OpenAI-only) | ✅ |
| `git_commit` | str | `git rev-parse HEAD` | ⚠️ |
| `limits` | obj | snapshot of the 7 `config.py` constants (§4) | ⚠️ |
| `started_at` / `ended_at` | ISO8601 | harness | ⚠️ |
| `sandbox` | enum | `docker`\|`local-gateway` | ✅ |

**Record both model roles separately.** `cli.py --model` sets orchestration and
worker to the same id, but they are distinct knobs (`models.py`, `Role =
Literal["orchestration", "worker"]`). Logging one field would silently lose that.

---

## 3. Outcome

| Field | Type | Source | Status |
|---|---|---|---|
| `final_answer` | str | `cli.run()` → `answer` | ✅ |
| `correct` | 0\|1 | grader vs `answer_rubric` | ⚠️ |
| `grader` | enum | `llm-judge`\|`exact` | ⚠️ |
| `grader_rationale` | str | judge output — keep for audit | ⚠️ |
| `route` | enum | `DIRECT`\|`CLARIFY`\|`PLAN` — first line of the `planner_agent` message in state | ✅ dumped (`outcome.route`, `outcome.routes[]`) |
| `degraded_to_direct` | bool | `Planner retries exhausted:` in the planner message — see below | ✅ dumped (`outcome.degraded_to_direct`) |
| `reached_reporter` | bool | `[reporter_agent]` present in trace | ⛏ |
| `terminal_state` | enum | `completed`\|`crashed`\|`timeout`\|`recursion-limit` | ⛏ + exit code |
| `exit_code` | int | CLI rc (`run_problem.sh:34`) | ✅ |

Rubrics are **all-or-nothing** ("Do not award partial credit"), so `correct` is
binary. Grade with an LLM judge — the answers are prose and free-form lists
(`hb017` answered `Sample_10_Group2`, the rubric says `Sample_10`; string
equality would wrongly fail it). Precedent to reuse:
`demo/score_hypothesis_recovery.py`.

**`degraded_to_direct` is not cosmetic.** When planner format-retries exhaust, the code forces
`response.content = "ROUTE: DIRECT\n\nPlanner retries exhausted: ..."` — and in
the same return **resets `planner_retry_count` to 0**
(`plan_output.py:214-219`, and identically at `:250`, `:276`). So a run that
burned both retries and collapsed to DIRECT ends with state claiming zero
planner retries. It is a failed run wearing a successful route's clothes. The *counter* cannot see
it — but the forced content is assigned to `response.content` (`plan_output.py:214`)
and that object is committed to state, so the dump reads it off the planner's
message. No mining needed.

The anchor is a *code* literal, not prompt copy, so it is stable. The
co-emitted `logging.error("planner_state_update: %s", ...)` (`plan_output.py:213`)
remains a free cross-check in the log. No flag needs adding to the exhaustion
branch — that would mean changing the reset behaviour, a real control-flow
change, for information the message already carries.

---

## 4. Cost & efficiency

`usage_tracker` already accumulates all of this per-agent **and** per-step
(`src/server/usage_tracker.py`, recorded at `src/graph/node_factories.py:117`
around every `agent_model.invoke()`). It is a live singleton, serialized only to
the WebSocket UI (`src/server/routes/chat.py:160`) and **never written to disk**.

| Field | Type | Source | Status |
|---|---|---|---|
| `wall_time_s` | float | `cli.py:309-311` (already printed at `:343`) | ✅ |
| `input_tokens` / `output_tokens` / `total_tokens` | int | `usage_tracker.to_dict()` | ✅ |
| `llm_calls` | int | `usage_tracker` | ✅ |
| `by_agent{}` | obj | `to_dict()["agents"]` — per planner/recruiter/manager/evaluator/reporter/coding | ✅ |
| `by_step[]` | list | `to_dict()["steps"]` — `step_id, agent_name, tokens, time, llm_calls` | ✅ |
| `est_cost_usd` | float | ○ price table × tokens, at analysis time | ○ |

**Decision: do not compute dollar cost at run time.** No pricing table exists in
the repo (no tiktoken/litellm). Prices change; tokens don't. Store tokens, price
them in the analysis notebook.

Token accounting is cross-provider safe: `record_llm_call` reads LangChain's
`AIMessage.usage_metadata`, which populates `input_tokens`/`output_tokens` for
both Anthropic and OpenAI (`usage_tracker.py:53-58`). **Caveat to verify once
before the full sweep:** cache-read/cache-write and reasoning tokens may not be
in that dict; if Claude prompt-caching is active, input_tokens may undercount
true billed volume. Confirm on a pilot run before trusting cost comparisons.

---

## 5. The three troubleshooting layers

The three loops are defined in `src/config.py:135-153` ("the three
execution-control loops"). Record **triggers, successes, and limit-hits** for
each — a raw count alone can't distinguish "recovered twice" from "thrashed
twice and gave up".

### Limits snapshot (record with every run — these are tuning knobs)

| Constant | Value | Layer |
|---|---|---|
| `MAX_EXECUTOR_RETRIES` | 15 | 1 |
| `EXECUTOR_RECURSION_LIMIT` | 60 | 1 backstop |
| `MAX_STEP_RETRIES` | 3 | 2 |
| `MAX_REPLANS` | 2 | 3 |
| `MAX_PLANNER_RETRIES` | 2 | validation |
| `MAX_RECRUITER_RETRIES` | 2 | validation |
| `RECURSION_LIMIT` | 100 | global |

### Layer 1 — Executor self-correction (`coding_agent/model.py`)

Innermost: a code cell raised / timed out / kernel unreachable. Counter is
`_exec_state["consecutive_errors"]`, **reset on success** and reset per step
invocation.

| Field | Type | Status |
|---|---|---|
| `exec_failures_total` | int | ⛏ |
| `exec_success_total` | int | ⛏ |
| `exec_recovered_total` | int — failures followed by a success in the same step | ⛏ |
| `exec_limit_hits` | int — steps that spent the budget of 15 | ⛏ |
| `exec_max_consecutive` | int — deepest hole dug in any one step | ⛏ |
| `exec_failures_by_kind{}` | obj — `traceback`\|`timeout`\|`kernel-unreachable` | ⛏ |

**Mine this layer; do not build an accumulator.** The in-memory counter is
destroyed on reset, so state can't be dumped — but the coding agent logs every
execution (`python tool executing:` / `python tool output:`, `logging.info` in
`coding_agent/model.py`) and those land in `full_stdout.log` because
`run_problem.sh:33` merges stderr with `2>&1`. Ordering is preserved, so
consecutive-failure runs and recoveries are reconstructable. Measured on the
existing archive: hb001 = 30 executions / 25 tracebacks, hb017 = 16 / 15.

Three caveats, all real:
- **The `2>&1` merge is load-bearing.** Drop it and this layer becomes
  unminable. Pin it in the harness.
- **Tool output is truncated at `MAX_OUTPUT_CHARS = 3000`** (`config.py:130`),
  which can cut a traceback and hide the exception type. `exec_failures_by_kind`
  is therefore best-effort; the totals are sound.
- **`sandbox.py:65-66` carries a structured error flag** precisely so the agent
  can count failures "without sniffing the text". Mining re-derives by sniffing
  text what the runtime already knows cleanly. Accepted trade: the text is free,
  the flag costs an invasive change.

### Layer 2 — Manager `retry_step` (`manager_agent/tools.py:184-225`)

| Field | Type | Status |
|---|---|---|
| `steps_total` | int | ✅ plan store |
| `step_retries_total` | int — Σ per-step `retry_count` (`plan_store.py:102`) | ✅ |
| `steps_retried` | int — distinct steps with `retry_count > 0` | ✅ |
| `step_retry_limit_hits` | int — steps with `retry_count >= MAX_STEP_RETRIES` | ○ from state |
| `steps_failed` | int — final status `failed` | ✅ |
| `step_retry_recovered` | int — retried steps ending `completed` | ○ from state |
| `step_retry_reasons[]` | list — `retry_step`'s `task_instructions` args, in state | ✅ dumped (`loops.manager.step_retry_reasons`) |

The plan store persists `retry_count` **and** `status` per step, so the
per-step counts above fall out of the dump — no instrumentation. Only the
*reason* text needs mining (the `task_instructions` on each `→ retry_step(...)`
trace line).

**But the plan-store counters are not the run-level total, and undercount
twice.** (a) A replan makes the planner rewrite plan.md, so every `retry_count`
is zeroed — the dump then describes only the *final* plan iteration, and a run
that retried three times before replanning reports zero. (b) A retry refused at
the `MAX_STEP_RETRIES` budget returns an error string **without** incrementing
anything (`manager_agent/tools.py:203-212`), so the retries that mattered most
leave no trace in the counter. The message history survives both — it
accumulates across replans and records refused calls — so the run-level total is
counted from state messages instead (`loops.manager` in the dump: `retry_step_calls`,
`retry_step_refused`, `retry_step_dispatched`, `next_step_calls`). Keep both:
`plan.*` describes the final plan, `loops.manager` describes the whole run.

### Layer 3 — Evaluator replan (`graph.py:364-397`)

| Field | Type | Status |
|---|---|---|
| `replans_triggered` | int — `replan_count` from state | ✅ **dump, never mine** |
| `replan_limit_hit` | bool — `replan_count > MAX_REPLANS` | ○ from state |
| `replan_history[]` | list of ISO timestamps (`graph.py:371`) | ✅ |
| `replans_successful` | int — see definition | ✅ dumped (verdicts read from state messages) |
| `replan_reason_code[]` | list — raw text dumped (`loops.replan_reasons`); the code is assigned post-hoc | ✅ / ○ |

**`replans_triggered` must come from the dump, not the trace — the trace
undercounts it.** `node_factories.py:104-107` runs `state_update_fn` *before*
`emit_message`, deliberately, so that when the cap is hit the evaluator's
in-place rewrite to `ROUTE: REPORT` (`graph.py:372-382`) is what the trace sees.
The third `ROUTE: REPLAN` **never appears in the log**, while state correctly
holds `replan_count == 3`. Mining would report 2. The error lands precisely on
the runs that failed hardest — the ones the whole metric exists to find. State
is authoritative and free; use it.

This also dissolves the earlier plan to add a `replan_limit_hit` flag and to
string-match `"Replan limit reached"`: `replan_count > MAX_REPLANS` is exact,
and both are already in state.

**Definition — "replan successful":** replan *k* is successful iff the next
evaluator verdict is a **genuine** `ROUTE: REPORT` — the blocker was resolved,
not the loop cut off. Not successful if the next verdict is another `REPLAN`, or
if it is the forced REPORT at the cap. Then reconcile against `replan_count`: if
the observed REPLAN count is one short of state, the final replan was the capped
one and is by definition unsuccessful. **A mismatch other than this known
off-by-one means the reader is broken.**

**Read the verdict sequence from state, not from the log.** `node_factories.py:104`
sets `response.name = agent_node_id` before the message is committed, so every
evaluator verdict is identifiable in `state["messages"]` by `name ==
"evaluator_agent"` — no substring matching, and therefore none of §8.2's
prompt-echo false positives (the naive grep scores 8 on every run, including
26-second DIRECT runs that never construct an evaluator). The dump computes
`replans_successful`, `evaluator_verdicts[]`, `forced_report_at_cap`, and
`verdict_state_mismatch` (null unless the delta is something other than 0 or 1)
directly. The in-place rewrite caveat still applies to the *sequence* — state's
`replan_count` remains the authority on how many replans fired.

Also record the run-level rollup `replan_rescued: bool` — run had ≥1 replan and
ended `correct == 1`. That answers "does replanning save runs?", which
per-replan success does not.

### Validation-retry loops (adjacent, count separately)

| Field | Source | Status |
|---|---|---|
| `planner_retries` | count of the planner's retry-feedback messages (`plan_output.py:221,256,282`) — survives the reset | ✅ dumped (`loops.planner_format_retries`; the raw counter is kept as `planner_retries_state_counter`) |
| `planner_retry_exhausted` | same signal as `degraded_to_direct` | ✅ dumped |
| `recruiter_retries` | `recruiter_retry_count` (`graph.py:331`) | ✅ |
| `recruiter_retry_exhausted` | proceeds to manager anyway | ⛏ |

These are **output-format** failures, not task failures. Folding them into the
three layers would conflate "the model can't emit valid JSON" with "the analysis
was wrong" — a distinction that matters when comparing GPT to Claude.

---

## 6. Failure & replan taxonomies

Free text does not aggregate. Record **both** the raw text (audit) and a
categorical code (counting). Codes are assigned post-hoc by an LLM classifier
over the raw text, so the enum can be revised without re-running.

`failure_mode` — set when `correct == 0`:

| Code | Meaning |
|---|---|
| `wrong-answer` | pipeline completed, answer incorrect |
| `code-error-unrecovered` | Layer 1 budget spent |
| `kernel-timeout` | execution exceeded limit |
| `data-load-failure` | never read the input |
| `hallucinated-evidence` | markers/genes not in the data |
| `format-violation` | answer unparseable vs rubric |
| `replan-limit-exhausted` | Layer 3 cap hit |
| `recursion-limit` | global backstop |
| `degraded-to-direct` | forced DIRECT (§3) |
| `infra-error` | API/5xx/OOM — **excluded from success rate** (§7) |

`replan_reason_code` / `step_retry_reason_code`:

| Code | Meaning |
|---|---|
| `insufficient-evidence` | conclusion unsupported |
| `wrong-tool-or-agent` | recruiter mis-assignment |
| `step-produced-no-output` | expected artifact missing |
| `contradictory-results` | steps disagree |
| `data-misread` | wrong file/axis/orientation |
| `plan-too-shallow` | plan under-specified the task |

---

## 7. Derived metrics (analysis time — never stored)

| Metric | Definition |
|---|---|
| `success_rate` | mean `correct`, overall + per bucket + per `human_solvable` |
| `pass@1` / `pass@3` | mean over seeds / any-of-3 |
| `tokens_per_correct` | Σ tokens ÷ Σ correct — the real efficiency comparator |
| `layer{1,2,3}_invocation_rate` | runs invoking layer ≥1 time ÷ eligible runs |
| `replan_success_rate` | `replans_successful` ÷ `replans_triggered` |
| `exec_recovery_rate` | `exec_recovered_total` ÷ `exec_failures_total` |
| `direct_route_rate` | DIRECT ÷ all (excluding `degraded_to_direct`) |
| `failure_mode_distribution` | histogram, per model |

**Normalize layer rates over PLAN-route runs only.** DIRECT and CLARIFY
short-circuit to `END` (`graph.py:279-301`) — no recruiter, manager, or
evaluator ever runs, so those runs have zero replans/retries *by construction*.
Including them in the denominator makes a model that short-circuits often look
robust rather than merely evasive. `direct_route_rate` is itself a headline
comparison metric between GPT and Claude.

**Exclude `infra-error` runs from success rate; report the count separately.** A
529 that killed a run is not evidence about the model's biology.

---

## 8. Acquisition: one dump + a miner

### 8.1 The only code change

> **Status (2026-07-25): (1) is implemented.** `cli.py` writes `metrics.json`
> (schema_version 1) to the active project dir at run end, plus `--metrics-out
> PATH` for the harness; `--task-id` / `--seed` are passed through verbatim.
> Sections: `run` (ids, git sha, sandbox, timestamps, wall time) · `models`
> (both roles) · `limits` (§5 snapshot) · `outcome` (incl. `route`, `routes[]`,
> `degraded_to_direct`) · `usage`
> (`usage_tracker.to_dict()` + totals) · `loops` (`replans_triggered`,
> `replans_successful`, `replan_limit_hit`, `replan_history`,
> `evaluator_verdicts[]`, `forced_report_at_cap`, `verdict_state_mismatch`,
> `replan_reasons[]`,
> `manager.{retry_step_calls,retry_step_refused,retry_step_dispatched,next_step_calls,step_retry_reasons[]}`,
> `planner_format_retries`, `planner_retries_state_counter`, `recruiter_retries`) · `plan` (per-step status +
> `retry_count` rollups). Runtime is `run.wall_time_s`, with
> `usage.llm_time_seconds` and per-agent / per-step splits alongside it. It is
> also written on the failure path, with `terminal_state` ∈
> `completed|crashed|recursion-limit|interrupted` and state recovered from the
> checkpointer. `run_problem.sh` archives it alongside `chat.json` (the
> structured session trace — previously destroyed by the next run's
> `clear_active_project_dir()`). Tests: `tests/test_run_metrics.py`.
> Still open: (2) the harness/grader and the §8.2 miner.

| # | Change | Where | Effort |
|---|---|---|---|
| 1 | Dump `metrics.json` at run end | `cli.py:345-351` | ~1 h |
| 2 | Harness: (task × model × seed) loop + LLM-judge grader | `benchmark/biomysterybench/biomysterybench_expr/` | ~4 h |

(1) is **purely additive**: append keys to the dict already returned by
`cli.run()`. It touches no control flow, no prompt, no graph node — it reads
state that already exists at run end and writes a file. Everything it carries:

- `usage_tracker.to_dict()` — **the only source of token data anywhere.** Not in
  the trace, not reconstructable. This alone justifies the change.
- `replan_count`, `replan_history` — already read at `cli.py:333-334`.
- plan-store steps: `retry_count`, `status` per step.
- `elapsed`, `route`, model selection, limits snapshot.

The previously-planned executor accumulator, `replan_history` upgrade,
`replan_limit_hit` flag, and manager reason instrumentation are all **dropped** —
mining or existing state covers them.

### 8.2 Mining rules — and why naive grep is provably wrong

**Substring `grep` of the trace does not work.** Measured across the four
archived runs, every single one reports identical counts:

| Run | route | naive `grep -c 'ROUTE: REPLAN'` | actual replans |
|---|---|---|---|
| hb001 | PLAN | 8 | 0 |
| hb017 | PLAN | 8 | 0 |
| hb006 | DIRECT | 8 | 0 |
| reci6… | DIRECT | 8 | 0 |

`reci6` is a 26-second DIRECT run that short-circuits to `END` and never
constructs an evaluator — it cannot have replanned. The identical `8` across
four unrelated runs is the tell: **the agents' own system prompts are echoed
into `full_stdout.log`**, and the evaluator's prompt contains the literal string
`ROUTE: REPLAN` eight times as instructions to itself. Same trap for
`retry_step` (6 matches in every run, all from the manager's tool docs; actual
invocations: 0).

**Anchor every pattern to trace structure, not content.** `_drain_trace`
(`cli.py:113-148`) prints agent messages as `[<agent_name>] <text>` and tool
calls as `  → <tool>(<args>)`. Anchored at line start, these are unambiguous:

| Metric | Pattern |
|---|---|
| `route` | `^\[planner_agent\] ROUTE: (DIRECT\|PLAN\|CLARIFY)` |
| evaluator verdicts (ordered) | `^\[evaluator_agent\] ROUTE: (REPLAN\|REPORT)` |
| step dispatches | `^  → next_step\(` |
| step retries | `^  → retry_step\(` |
| executor executions | `python tool executing:` / `python tool output:` |

Verified against the archive, these give sane, run-varying values (hb001: PLAN,
3 `next_step`, 0 `retry_step`, 1 evaluator REPORT).

**Two structural limits of the trace, both accepted:**
- A message carrying *only* tool calls prints no `[agent]` header (`cli.py:126-129`
  prints the header only when `text` is non-empty), so `→ next_step(...)` lines
  carry no agent attribution. Safe here only because `next_step`/`retry_step` are
  uniquely manager-owned — an inference, not a fact in the log.
- Only the first line of multi-line content gets the header. Fine for ROUTE
  verdicts (the header is line 1 by prompt contract) — do not rely on it for
  anything deeper.

**Mining couples metrics to prompt copy and log format.** Reword the evaluator
prompt and the false-positive surface shifts; change `_drain_trace`'s format and
every anchor breaks — silently, producing plausible numbers. Mitigation: the
miner must **assert against the dump** (§5, Layer 3) and fail loudly on
mismatch, not shrug.

### 8.3 Validation gap

**None of the four archived runs contains a single replan, step retry, or
executor-limit hit** — the recovery machinery has never fired in the data we
have. The miner's Layer 2/3 logic therefore cannot be validated against real
positives yet. Before trusting it, force a failure (point a task at a corrupt
input, or temporarily set `MAX_STEP_RETRIES = 1`) and confirm the miner and the
dump agree.

**Runtime cost of the sweep.** hb001 took 43.6 min; the top 5 tasks are 91% of
the 57.2 GB corpus. 204 runs is plausibly 60–100 CPU-hours. Runs are sequential
per node (shared `workspace/` + kernel-gateway port 8888 —
`slurm/run_bmb.sbatch:11-16`); parallelism requires one job per node. Consider a
pilot on ~8 cheap tasks × 2 models × 3 seeds first, to validate the schema and
the token-metadata caveat (§4) before committing the full sweep.

---

## 9. Open decisions

1. **Which exact model ids?** Default is `gpt-5.1` (`models.py:59-64`). Pick the
   Claude counterpart and decide native providers vs both via OpenRouter (one
   path = fewer confounds; native = truer to production).
2. **Swap both roles or hold `worker` fixed?** Swapping both measures the model
   family end-to-end; holding worker fixed isolates orchestration quality.
   Recommend swapping both, and logging each (§2).
3. **Judge model.** Using either contestant to grade itself is a conflict —
   recommend a third model, or hand-grade the 34 gold answers once.
4. **Is `hb006` gradeable?** Its rubric expects all of `Sample_1..45`; the run
   answered a scattered 100+ set. Confirm the rubric matches the shipped data
   before it counts as a legitimate miss.
