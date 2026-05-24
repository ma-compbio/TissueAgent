# Copilot Mode + Skill Registry — Implementation Plan

## Decisions locked in

| # | Decision |
|---|---|
| Plan template format | YAML (unchanged for now; markdown migration is future work) |
| Live plan format | Markdown — `sessions/active/plan.md` with `## Step N — Title` + YAML fence (already in place) |
| Mode | Two modes — **autopilot** (default; only mode in notebook/terminal) and **copilot** (app-only) |
| Plan editing | In-app UI editor only (no on-disk hand-edits as a supported flow) |
| Pause mechanic | LangGraph `interrupt_before` on recruiter + manager nodes (cleanest) |
| Edit channel | One `## Step N` section per step (editable, diffable) |
| Recruiter re-run | After plan edit, edits go **directly to Recruiter** (Planner not re-invoked unless user uses "feedback → REPLAN" path) |
| Mode toggle | Persistent sidebar toggle (per-session, survives reloads) |
| Skill registry | Scaffold only this round — empty `src/skill_registry/` + README + schema doc, no loader, no wiring |
| Template migration | Deferred — separate diff after copilot lands |
| Backwards compat | None needed — the live plan is already markdown (`plan_store.py`); schema reserves `approved`/`paused` for this work |

---

## Milestone 1 — Mode infrastructure (foundations)

Goal: introduce the autopilot/copilot mode concept end-to-end without changing graph behavior yet.

- [x] Add `mode: Literal["autopilot", "copilot"]` to session state (server-side) — `session_manager.py` (`SessionMode`, `SessionState.mode`)
- [x] Default to `autopilot`; force `autopilot` when not running under the app frontend (notebook/CLI entry points) — mode lives only on the server's `SessionState`; notebooks/CLI build the graph directly and never set up that session, so they cannot opt in. Documented in `graph.py` docstring.
- [x] Persist mode on the session record so it survives reloads — `save_session` / `load_session` (utils.py), wired through `/api/sessions/save` + `/api/sessions/load`. Note: live mode-update-after-load is deferred; the loaded mode takes effect on next WS reconnect.
- [x] Expose mode over the WebSocket connect payload + `/api/session` response — `mode_updated` event on connect (chat.py); REST `/api/sessions/mode` (GET+POST) in sessions.py
- [x] Frontend: add `mode` to the session store / context — `useWebSocket` exposes `mode` + `setMode`; types in `messages.ts` (`SessionMode`, `SetModeEvent`, `mode_updated` server event)
- [x] Frontend: add persistent sidebar toggle in `Sidebar.tsx` (Autopilot / Copilot pill) — wired through `App.tsx`; CSS in `index.css` (`.mode-toggle`, `.mode-pill`). Disabled while `isRunning`.
- [x] Frontend: emit a `set_mode` WebSocket message; server updates session and acks — `_handle_set_mode` in chat.py refuses mid-run changes and echoes `mode_updated`
- [x] Smoke test: Python imports + reset() preserves mode + TypeScript compiles clean

**Exit criterion:** mode is plumbed everywhere but does nothing functional yet. ✅

---

## Milestone 2 — Live plan schema extensions

Goal: extend `plan_store.py` so the markdown plan supports the new statuses and edit metadata that copilot needs.

- [x] Extend `PlanDocStatus` with `awaiting_plan_review`, `awaiting_assignment_review` (in addition to existing `draft`, `recruited`, `approved`, `running`, `paused`)
- [x] Add `last_edited_by: Literal["planner","recruiter","manager","user"] | None` to `PlanDocument` (`EditedBy` type alias)
- [x] Add `last_edited_at: str | None` (ISO-8601 UTC timestamp) to `PlanDocument`
- [x] Update `to_markdown()` to write the new header fields in the YAML fence — emitted only when set so legacy plans round-trip unchanged
- [x] Update `_parse_markdown()` to read them (default `None` for old files)
- [x] Add `apply_user_edit(markdown: str) -> PlanDocument` helper on `PlanStore` — parses, validates, stamps `user` + timestamp, re-serialises through `to_markdown()` so on-disk form is normalised. Raises `PlanEditError` on malformed input.
- [x] REST `/api/plan` and `serialize_plan` updated to surface the new fields
- [x] Tests in `tests/test_plan_store.py` — round-trip idempotency, user edit (rename + reorder), malformed input rejection (file untouched), new metadata round-trip, legacy plan loads clean. All 5 pass.

**Exit criterion:** plan store handles all states and a safe user-edit path, with no graph wiring yet. ✅

---

## Milestone 3 — Graph interrupts

Goal: wire LangGraph `interrupt_before` on recruiter and manager nodes, gated by mode.

**Design note:** rather than baking `interrupt_before` into the compiled graph (which would require recompiling on mode toggle), I compile once with a checkpointer and pass `interrupt_before` *at invoke time* — copilot only. Autopilot omits it entirely. This means the same compiled graph drives both modes.

- [x] Checkpointer wired in main.py — `graph.compile(checkpointer=MemorySaver())`
- [x] `interrupt_before=[recruiter_agent, manager_agent]` passed at invoke time when `session.mode == "copilot"` (chat.py `_run_graph`)
- [x] `SessionState` gains `thread_id` (cycled per user turn) and `paused_at` for tracking active interrupt
- [x] After invoke returns, `compiled.get_state(config).next` is checked. Tuple containing `recruiter_agent` → pause label `before_recruiter`; `manager_agent` → `before_manager`; empty → run completed.
- [x] On pause: `plan_store` status flips to `awaiting_plan_review` / `awaiting_assignment_review`; `plan_updated` event fires; `plan_review_requested` / `assignment_review_requested` event fires.
- [x] Resume scaffolding: `plan_approved` / `assignments_approved` WS messages call `_handle_resume(expected_pause=...)` which invokes the graph with `input=None`. Edit + feedback paths are deferred to Milestone 4.
- [x] Synthetic mechanics tests in `tests/test_interrupt_mechanics.py` lock in: autopilot runs through; copilot pauses before recruiter; first resume runs recruiter and pauses before manager; second resume completes; per-`thread_id` isolation works.
- [x] Plan store tests still pass (no regression).

**Exit criterion:** copilot graph pauses correctly at both gates; autopilot graph still runs through. ✅ (mechanics verified via synthetic graph; real-graph copilot run needs Milestone 5's UI to be exercised end-to-end interactively.)

---

## Milestone 4 — Resume protocol (WebSocket)

Goal: define the messages that flow between the frontend review UI and the graph when paused.

**Design note:** for `*_feedback` we chose the simpler "both rewind to planner" pattern. Both feedback events append a `HumanMessage` with the user text, cycle the `thread_id`, reset the on-disk plan, and re-invoke from the top. The planner can then decide whether to actually re-plan or pass through. This matches how the existing REPLAN loop works.

- [x] Inbound message types in `frontend/src/types/messages.ts`: `PlanApprovedEvent`, `PlanEditedEvent`, `PlanFeedbackEvent`, `AssignmentsApprovedEvent`, `AssignmentsEditedEvent`, `AssignmentsFeedbackEvent`, `RunCancelledClientEvent`
- [x] Outbound message types in `ServerEvent`: `plan_review_requested`, `assignment_review_requested`, `run_cancelled`
- [x] Server handlers in `chat.py`: `_handle_plan_edited`, `_handle_assignments_edited` (both call `_apply_user_plan_edit_and_resume`); `_handle_plan_feedback`, `_handle_assignments_feedback` (both call `_rewind_to_planner_with_feedback`); `_handle_run_cancelled`
- [x] Shared gate validator `_require_paused_at` returns clear `WrongPauseGate` / `NotPaused` errors and leaves session state untouched on rejection
- [x] Frontend `useWebSocket` exposes `reviewState`, `approvePlan`, `editPlan`, `sendPlanFeedback`, `approveAssignments`, `editAssignments`, `sendAssignmentsFeedback`, `cancelRun`. Review state is driven by incoming `*_review_requested` events; cleared on `run_complete` and `run_cancelled`.
- [x] Tests in `tests/test_resume_protocol.py` — 12 tests covering: approve gates (right + wrong + not-paused); plan_edited persists + resumes + handles malformed input; assignments_edited uses the right gate; feedback appends message + cycles thread + resets plan + rejects empty text; cancel clears state + still acks when nothing pending. All pass.
- [x] No regressions in earlier test suites (plan_store, interrupt mechanics — 10 tests still pass)

**Exit criterion:** all seven inbound + three outbound messages work end-to-end. ✅ (handler-level verified; the UI for approve/edit/feedback buttons lands in Milestone 5.)

---

## Milestone 5 — Frontend review panels

Goal: extend `PlanPanel.tsx` to support the review/edit UI at both gates.

**Design note:** `reviewState` lives on `useWebSocket` (kept there in Milestone 4 since the WS layer is the source of truth for `*_review_requested` events). `usePlan` was *not* extended — it stays a pure data hook.

- [x] `reviewState: "plan" | "assignment" | null` exposed by `useWebSocket` (added in M4); cleared on `run_complete` / `run_cancelled`
- [x] Driven by inbound `plan_review_requested` / `assignment_review_requested` events
- [x] When `reviewState === "plan"`, PlanPanel shows:
  - Approve button → `approvePlan()`
  - Edit toggle → reveals a markdown textarea pre-filled with current markdown; Save → `editPlan(markdown)`, Discard → revert local buffer
  - Feedback textarea + Send → `sendPlanFeedback(text)` (disabled when empty)
  - Cancel run button → `cancelRun()`
- [x] When `reviewState === "assignment"`, PlanPanel shows:
  - Approve button → `approveAssignments()`
  - Per-step `assigned_agent` dropdown populated from `/api/agents`
  - Save assignments → `updateAssignmentsInMarkdown` serialises picks back into plan markdown (mirrors `PlanDocument.to_markdown`), then `editAssignments(markdown)`
  - Feedback textarea + Send → `sendAssignmentsFeedback(text)`
  - Cancel run → `cancelRun()`
- [x] Autopilot mode never shows review controls because `reviewState` is only ever set from copilot pause events
- [x] `last_edited_by: "user"` surfaces as an "edited by you" badge next to the status
- [x] `PlanStatus` extended with `awaiting_plan_review` and `awaiting_assignment_review`; CSS gives both an accent-light highlight
- [x] New endpoint `GET /api/agents` returns `[{id, name, description}]` from `AgentDefns`. `useAgents()` hook fetches once on mount.
- [x] CSS added: `.plan-review-bar`, `.plan-action-btn (primary/danger)`, `.plan-edit-view`, `.plan-edit-textarea`, `.plan-edit-actions`, `.plan-review-feedback-input`, `.plan-step-agent-select`, `.plan-edit-badge`
- [x] TypeScript `tsc --noEmit` clean; 22 backend tests still pass (no regressions)

**Manual QA still needed** (interactive, requires a live LLM):
- Autopilot run shows plan progress, no review controls
- Copilot plan gate: Approve resumes; Edit + Save resumes with new markdown; Feedback rewinds to planner; Cancel clears state
- Copilot assignment gate: same shape with dropdown changes for assigned_agent

**Exit criterion:** PlanPanel supports both review gates with approve / edit / feedback / cancel, autopilot hides all editing. ✅ (implementation + type-checks; interactive QA pending a live run.)

---

## Milestone 6 — Skill registry scaffold

Goal: lock in the directory layout for future skills without wiring anything.

**Location note:** placed at `src/agents/skill_registry/` to match the existing pattern (`src/agents/agent_registry/`, `src/agents/planner_agent/plan_registry/`) rather than at the top-level `src/skill_registry/` the plan originally suggested.

- [x] Created `src/agents/skill_registry/` containing the README that defines the schema and future-work boundary
- [x] `src/agents/skill_registry/README.md` documents:
  - What a skill is vs. an agent vs. a plan template (comparison table)
  - The frontmatter schema: `name`, `description`, `applies_to: [agent_ids]`, `tags`
  - The body conventions (When to use / Steps / Pitfalls / References)
  - "Status: scaffold only" caveat — no loader, no agent consumes it
  - Explicit future-work list (lazy load tool, selector, schema linter, applies_to validation)
- [x] `.gitkeep` not needed — README.md keeps the directory tracked
- [x] Top-level README updated: tree now shows `skill_registry/` alongside `agent_registry/`, plus surfaces `plan_registry/` under `planner_agent/`

**Exit criterion:** directory exists, schema is documented, nothing is wired. ✅

---

## Milestone 7 — Verification + docs

Goal: catch regressions and document the new flow before shipping.

### Automated (this milestone)
- [x] All 22 backend tests pass: `test_plan_store` (5) + `test_interrupt_mechanics` (5) + `test_resume_protocol` (12)
- [x] `tsc --noEmit` clean
- [x] `npm run build` produces a fresh production bundle in `src/frontend/dist/` (replaces the May-15 stale build that was served on port 8000)
- [x] Top-level README gains an **Execution modes** section explaining autopilot vs copilot, where the toggle lives, the four review actions, and the "app-only" boundary
- [x] Recruiter prompt acknowledges user-edited plans (`last_edited_by: user` → treat user wording as authoritative)
- [x] Planner prompt unchanged — REPLAN loop already handles feedback, and copilot feedback arrives as a regular `[Copilot feedback from user] ...` HumanMessage that the planner will see naturally

### Interactive (deferred to user)
Documented in [`COPILOT_QA.md`](COPILOT_QA.md). Nine paths to walk through against a real LLM:
- [ ] Autopilot regression (no pauses, no UI)
- [ ] Copilot plan gate — approve
- [ ] Copilot plan gate — edit + save + discard + reject-malformed
- [ ] Copilot assignment gate — approve + per-step dropdown edits
- [ ] Feedback rewinds to planner (+ empty-feedback rejection)
- [ ] Cancel clears state cleanly
- [ ] Mode toggle persists across reload
- [ ] Mid-run toggle is blocked
- [ ] Notebook / CLI safety (mode field is server-only)

### Notes for the interactive QA
- Sidebar mode toggle is wired to `setMode` (chat.py `_handle_set_mode`); refuses mid-run changes
- Copilot pause status surfaces as `awaiting_plan_review` / `awaiting_assignment_review` with accent-light highlight; the four review actions appear in `.plan-review-bar`
- Edits stamp `last_edited_by: "user"` + ISO timestamp; "edited by you" badge appears next to the status
- Feedback prepends `[Copilot feedback from user] ` to the user's text so the planner can detect it via the existing REPLAN-style flow
- Cancelled runs reset `plan_store`, cycle `thread_id`, and clear `paused_at`

**Exit criterion:** both modes work end-to-end on real queries; docs reflect the new behavior. ✅ (automated portion landed; interactive QA checklist ready in `COPILOT_QA.md` for the user to run.)

---

## Out of scope (explicitly deferred)

- Converting plan templates from YAML to markdown
- Writing actual skills into `skill_registry/`
- Skill loader / per-agent skill discovery
- Editing the plan markdown file on disk (only in-app editing is supported)
- Pausing mid-execution (only between planner→recruiter and recruiter→manager); pausing inside the manager loop is a future "phase 3" feature already reserved in `PlanDocStatus`

---

## Open questions to revisit during implementation

- Should the feedback path (`plan_feedback`, `assignments_feedback`) be a free-text textarea, or structured (e.g. per-step comments)? Start with free-text; structure later if it proves clunky.
- Where does the "review requested" notification surface if the user has switched tabs? (Browser notification? Audio cue? For now: rely on the PlanPanel becoming the focus.)
- Should we record the human's edit diff in plan history for audit? Not in this round; revisit when sessions get persistent IDs.
