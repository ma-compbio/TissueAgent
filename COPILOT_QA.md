# Copilot Mode — Manual QA Checklist

Interactive smoke tests for the autopilot ↔ copilot feature. Run these against a real LLM in the web UI before merging.

## Setup

- [ ] Restart FastAPI server (so checkpointer + new routes pick up): `cd src && uvicorn server.main:app --reload --host 0.0.0.0 --port 8000`
- [ ] Either run the Vite dev server (`cd src/frontend && npm run dev` → open `http://localhost:5173`) **or** use the rebuilt prod bundle at `http://localhost:8000`. The Vite dev server is recommended — hot reload + cleaner errors.
- [ ] Verify the sidebar shows the **Autopilot / Copilot** pill toggle (between the model picker and the file-browser button).
- [ ] Verify the connection-status dot is green.

---

## Path 1 — Autopilot regression

Goal: confirm that turning on the checkpointer + thread_id did not break the existing happy path.

- [ ] Sidebar mode shows **Autopilot** (default).
- [ ] Upload a dataset, send a query that needs a plan (e.g. "Annotate cell types in the uploaded spatial dataset").
- [ ] Planner emits ROUTE: PLAN, plan panel populates with steps.
- [ ] Recruiter annotates assignments — plan panel updates inline.
- [ ] Manager runs the steps — sub-agent traces stream into the chat.
- [ ] Run finishes with the reporter's final message; elapsed seconds appear.
- [ ] No "awaiting your review" status anywhere. No approve/edit/feedback buttons. No pauses.

If any of the above misbehaves, the regression is in Milestones 3–5, not in copilot specifically.

---

## Path 2 — Copilot plan gate (approve)

- [ ] Toggle sidebar to **Copilot**. Mode pill highlights "Copilot".
- [ ] Send the same kind of query as Path 1.
- [ ] After the planner finishes:
  - Plan panel status shows **"awaiting your review"** with the accent-light highlight.
  - A review action bar appears with **Approve plan / Edit / Cancel run** buttons and a feedback textarea.
- [ ] Click **Approve plan**.
- [ ] The graph resumes: recruiter runs, plan panel updates with assignments, then the assignment gate opens (Path 4 covers it).

---

## Path 3 — Copilot plan gate (edit + save)

- [ ] Same setup as Path 2; wait until plan-review controls appear.
- [ ] Click **Edit**. A markdown textarea pre-fills with the current plan.
- [ ] Modify a step's `**Description:** ...` text. Click **Save & resume**.
- [ ] An "edited by you" badge appears next to the status.
- [ ] The run resumes; recruiter sees the edited plan.

Negative cases to spot-check:
- [ ] Edit to empty / remove all step headings → server should reject with `PlanEditError`; the on-disk plan is untouched; you can retry.
- [ ] Click **Discard** instead of Save → textarea closes, no change persisted.

---

## Path 4 — Copilot assignment gate (approve + edit)

After Path 2/3 resumes past the plan gate:

- [ ] Recruiter finishes. Plan panel status flips to **"awaiting your review of assignments"**.
- [ ] Each step now shows an `<assigned agent>` dropdown populated from `/api/agents` (9 options).
- [ ] Approve path: click **Approve assignments**. Manager runs, plan progresses normally to done.
- [ ] Edit path (run a separate query for this):
  - Change one or more step assignments via the dropdown.
  - Click **Save assignments**.
  - Manager runs with the new assignments; verify the chosen agent actually executes that step.

---

## Path 5 — Feedback rewinds to planner

- [ ] In a fresh copilot run, reach either the plan gate or the assignment gate.
- [ ] Type into the **feedback textarea** (e.g. "use a UMAP plot instead of a spatial scatter").
- [ ] Click **Send feedback**. A new HumanMessage appears in the chat: `[Copilot feedback from user] use a UMAP plot instead of a spatial scatter`.
- [ ] The planner re-runs. New plan appears. Either gate opens again for review.

Negative case:
- [ ] Empty feedback (whitespace only) → "Send feedback" button stays disabled. If somehow sent, server replies with `EmptyFeedback` error.

---

## Path 6 — Cancel

- [ ] In a fresh copilot run, reach the plan gate.
- [ ] Click **Cancel run**.
- [ ] Review controls disappear. Plan panel returns to empty. No run is active.
- [ ] You can immediately send a new query — it should work normally.

---

## Path 7 — Mode persistence

- [ ] Toggle to **Copilot**. Refresh the browser.
- [ ] On reconnect, the sidebar still shows **Copilot** (server sends `mode_updated` on connect).
- [ ] Toggle back to **Autopilot**. Refresh. Still Autopilot.

---

## Path 8 — Mid-run toggle is blocked

- [ ] Send a query in autopilot.
- [ ] **While the run is in flight**, try clicking the Copilot pill.
- [ ] The toggle button should be disabled (greyed out via `:disabled`). If somehow clicked, server replies with `ModeChangeBlocked` error.

---

## Path 9 — Notebook / CLI safety

- [ ] In a fresh Python REPL or notebook, run a query through `create_tissueagent_graph(...)` directly.
- [ ] Confirm no pauses occur even if `session.mode == "copilot"` were somehow set — notebooks never touch the server's session, so this should be impossible. Document any surprise.

---

## After QA

If everything passes:
- [ ] Tick the QA section in `COPILOT_PLAN.md` Milestone 7.
- [ ] Commit + open PR.

If something fails:
- Note the failing path and the observed behavior.
- The most likely culprit areas:
  - `src/server/routes/chat.py` — handler dispatch and graph driver
  - `src/server/plan_store.py` — markdown round-trip
  - `src/frontend/src/hooks/useWebSocket.ts` — event handling, reviewState lifecycle
  - `src/frontend/src/components/PlanPanel.tsx` — UI state
