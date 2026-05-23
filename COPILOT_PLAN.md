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

- [ ] Extend `PlanDocStatus` with `awaiting_plan_review`, `awaiting_assignment_review` (in addition to existing `draft`, `recruited`, `approved`, `running`, `paused`)
- [ ] Add `last_edited_by: Literal["planner","recruiter","manager","user"] | None` to `PlanDocument`
- [ ] Add `last_edited_at: str | None` (ISO timestamp) to `PlanDocument`
- [ ] Update `to_markdown()` to write the new header fields in the YAML fence
- [ ] Update `_parse_markdown()` to read them (default `None` for old files)
- [ ] Add `apply_user_edit(markdown: str) -> PlanDocument` helper on `PlanStore` that validates a user-submitted markdown blob, parses it, stamps `last_edited_by="user"` + timestamp, and writes
- [ ] Unit test: round-trip (write → read → write) is idempotent
- [ ] Unit test: user-edited markdown with renamed/reordered steps parses correctly
- [ ] Unit test: malformed user markdown returns a clear validation error, does not corrupt the file

**Exit criterion:** plan store handles all states and a safe user-edit path, with no graph wiring yet.

---

## Milestone 3 — Graph interrupts

Goal: wire LangGraph `interrupt_before` on recruiter and manager nodes, gated by mode.

- [ ] In `graph/graph.py`, add `interrupt_before=[recruiter_node_id, manager_node_id]` when compiling, **only when mode == "copilot"**
- [ ] Confirm checkpointer is configured (LangGraph interrupts require a checkpointer)
- [ ] Verify autopilot path is unchanged: end-to-end run from query to reporter with no pauses
- [ ] Verify copilot path: planner runs, graph stops before recruiter; check status flips to `awaiting_plan_review`
- [ ] After plan approval/edit, resume graph; recruiter runs, graph stops before manager; status flips to `awaiting_assignment_review`
- [ ] After assignment approval/edit, resume; manager runs to completion
- [ ] Add a small integration test that exercises both pause points

**Exit criterion:** copilot graph pauses correctly at both gates; autopilot graph still runs through.

---

## Milestone 4 — Resume protocol (WebSocket)

Goal: define the messages that flow between the frontend review UI and the graph when paused.

- [ ] Define inbound message types in `frontend/src/types/messages.ts`:
  - `plan_approved` (no payload — accept plan as-is)
  - `plan_edited` (payload: full markdown blob)
  - `plan_feedback` (payload: free-text → triggers REPLAN)
  - `assignments_approved`
  - `assignments_edited` (payload: full markdown blob with edited `assigned_agent` fields)
  - `assignments_feedback` (payload: free-text → re-runs recruiter with feedback)
  - `run_cancelled`
- [ ] Define outbound message types:
  - `plan_review_requested` (sent when graph hits `awaiting_plan_review`)
  - `assignment_review_requested` (sent when graph hits `awaiting_assignment_review`)
- [ ] Server-side handlers in `server/routes/chat.py` (or wherever WS messages are dispatched): for each inbound type, update plan via `plan_store`, then resume the graph with the appropriate next state
- [ ] For `*_feedback`, route back to the producing agent with the feedback string (Planner gets REPLAN, Recruiter gets a "user feedback" message)
- [ ] Handle `run_cancelled`: tear down the graph run cleanly
- [ ] Integration test: full copilot run with approve at both gates
- [ ] Integration test: copilot run with edits at both gates
- [ ] Integration test: copilot run with feedback → REPLAN at the plan gate

**Exit criterion:** all six inbound + two outbound messages work end-to-end.

---

## Milestone 5 — Frontend review panels

Goal: extend `PlanPanel.tsx` to support the review/edit UI at both gates.

- [ ] Add review state to `usePlan.ts` hook: `reviewing: "plan" | "assignment" | null`
- [ ] Drive `reviewing` from incoming `plan_review_requested` / `assignment_review_requested` messages
- [ ] When `reviewing === "plan"`, show plan-review controls in `PlanPanel`:
  - Approve button
  - Edit toggle → reveals a markdown textarea pre-filled with current plan markdown
  - Save edits button → emits `plan_edited`
  - Feedback textarea + send → emits `plan_feedback`
  - Cancel run button → emits `run_cancelled`
- [ ] When `reviewing === "assignment"`, show assignment-review controls:
  - Approve button
  - Per-step `assigned_agent` dropdown (populated from agent registry)
  - Save edits button → serialises the dropdown choices back into the plan markdown, emits `assignments_edited`
  - Feedback textarea + send → emits `assignments_feedback`
- [ ] Disable all review controls when `mode === "autopilot"` (panel becomes read-only)
- [ ] Visual indicator on each step: status badge (`pending` / `running` / `done` / `failed`), `assigned_agent` name
- [ ] When graph resumes after a review, clear `reviewing` state and show "in progress" status
- [ ] Manual QA: copilot run with approve, with edits, with feedback at each gate
- [ ] Manual QA: autopilot run shows plan progress without any review controls

**Exit criterion:** PlanPanel supports both review gates with approve / edit / feedback / cancel, autopilot mode hides all editing.

---

## Milestone 6 — Skill registry scaffold

Goal: lock in the directory layout for future skills without wiring anything.

- [ ] Create `src/skill_registry/` directory (empty)
- [ ] Add `src/skill_registry/README.md` describing:
  - What a skill is (shared prose playbook, not an executable tool)
  - The intended frontmatter schema: `name`, `description`, `applies_to: [agent_ids]`, `tags`
  - The body format (markdown with sections like "When to use", "Steps", "Pitfalls")
  - Explicit "future work" note: no loader exists yet; agents do not consult skills
- [ ] Add a single `.gitkeep` if needed so the empty directory is committed
- [ ] Mention skill registry alongside plan/agent registries in the top-level project README (one line)

**Exit criterion:** directory exists, schema is documented, nothing is wired.

---

## Milestone 7 — Verification + docs

Goal: catch regressions and document the new flow before shipping.

- [ ] Manual run: full autopilot session via app → matches pre-change behavior (no pauses, no review UI)
- [ ] Manual run: full copilot session via app → both review gates fire, edits and feedback work
- [ ] Notebook entry point: confirm it forces autopilot regardless of session setting
- [ ] CLI entry point: same
- [ ] Update top-level project README with a brief "Modes" section (autopilot vs copilot)
- [ ] Update planner / recruiter prompts if any wording needs to acknowledge that the user may have edited the plan (likely a 1-line addition to each prompt clarifying that edits are authoritative)
- [ ] Final regression sweep on existing flows: cell annotation, hypothesis generation, GO enrichment

**Exit criterion:** both modes work end-to-end on real queries; docs reflect the new behavior.

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
