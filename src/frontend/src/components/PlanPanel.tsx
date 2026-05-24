/**
 * Plan panel — read-only by default; copilot mode adds review controls.
 *
 * When ``reviewState === "plan"`` the panel exposes Approve / Edit / Feedback
 * / Cancel controls for the plan gate (between planner and recruiter).
 *
 * When ``reviewState === "assignment"`` it exposes per-step ``assigned_agent``
 * dropdowns and the same Approve / Feedback / Cancel pattern for the
 * assignment gate (between recruiter and manager).
 *
 * Outside of copilot reviews the panel is the same read-only view it has
 * always been — including showing the markdown source on demand.
 */

import { useEffect, useState } from "react";
import type { Plan, PlanStep } from "../hooks/usePlan";
import type { AgentInfo } from "../hooks/useAgents";
import type { PipelineStage, ReviewState } from "../hooks/useWebSocket";
import { PIPELINE_STAGES } from "../hooks/useWebSocket";

interface Props {
  plan: Plan;
  markdown: string;
  reviewState: ReviewState;
  pipelineStage: PipelineStage | null;
  agents: AgentInfo[];
  onApprovePlan: () => void;
  onEditPlan: (markdown: string) => void;
  onPlanFeedback: (text: string) => void;
  onApproveAssignments: () => void;
  onEditAssignments: (markdown: string) => void;
  onAssignmentsFeedback: (text: string) => void;
  onCancelRun: () => void;
}

const STAGE_LABELS: Record<PipelineStage, string> = {
  planner: "Planner",
  recruiter: "Recruiter",
  manager: "Manager",
  evaluator: "Evaluator",
  reporter: "Reporter",
};

const STATUS_LABEL: Record<string, string> = {
  empty: "no plan yet",
  draft: "draft — recruiter has not assigned agents",
  awaiting_plan_review: "awaiting your review",
  recruited: "ready — assignments complete",
  awaiting_assignment_review: "awaiting your review of assignments",
  approved: "approved",
  running: "running",
  paused: "paused",
  done: "done",
  failed: "failed",
};

export default function PlanPanel({
  plan,
  markdown,
  reviewState,
  pipelineStage,
  agents,
  onApprovePlan,
  onEditPlan,
  onPlanFeedback,
  onApproveAssignments,
  onEditAssignments,
  onAssignmentsFeedback,
  onCancelRun,
}: Props) {
  const [showSource, setShowSource] = useState(false);

  // Edit-mode markdown buffer for plan-gate edits.
  const [planDraft, setPlanDraft] = useState<string>("");
  const [editingPlan, setEditingPlan] = useState(false);
  // Per-step agent picks for the assignment gate (id → assigned_agent | null).
  const [assignmentDrafts, setAssignmentDrafts] = useState<
    Record<number, string | null>
  >({});
  // Free-text feedback buffers, one per gate.
  const [planFeedback, setPlanFeedbackText] = useState("");
  const [assignmentsFeedback, setAssignmentsFeedbackText] = useState("");

  // Reset local edit state whenever the review gate (re)opens.
  useEffect(() => {
    if (reviewState === "plan") {
      setPlanDraft(markdown);
      setEditingPlan(false);
      setPlanFeedbackText("");
    } else if (reviewState === "assignment") {
      const initial: Record<number, string | null> = {};
      for (const s of plan.steps) initial[s.id] = s.assigned_agent;
      setAssignmentDrafts(initial);
      setAssignmentsFeedbackText("");
    }
  }, [reviewState, markdown, plan.steps]);

  // ---------------------------------------------------------------------
  // Empty-state short-circuit
  // ---------------------------------------------------------------------

  if (
    (plan.status === "empty" || plan.steps.length === 0) &&
    reviewState === null
  ) {
    return (
      <div className="plan-panel">
        <div className="plan-panel-header">
          <span className="plan-panel-title">Plan</span>
          <span className="plan-panel-status plan-status-empty">
            no plan yet
          </span>
        </div>
        <div className="plan-panel-empty">
          Send a message that needs analysis — the planner will draft a plan
          here.
        </div>
      </div>
    );
  }

  const userEditedBadge =
    plan.last_edited_by === "user" ? (
      <span className="plan-edit-badge" title={plan.last_edited_at ?? ""}>
        edited by you
      </span>
    ) : null;

  const provenanceCaption = plan.provenance
    ? plan.provenance.source === "template"
      ? `From template: ${plan.provenance.template_id ?? "?"}${
          plan.provenance.version ? ` v${plan.provenance.version}` : ""
        }${
          plan.provenance.decision ? ` (${plan.provenance.decision})` : ""
        }${
          typeof plan.provenance.score === "number"
            ? `, score ${plan.provenance.score.toFixed(2)}`
            : ""
        }`
      : "De novo plan"
    : null;

  // ---------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------

  return (
    <div className="plan-panel">
      {reviewState !== null && (
        <ReviewBanner
          reviewState={reviewState}
          editingPlan={editingPlan}
          onApprovePlan={onApprovePlan}
          onApproveAssignments={onApproveAssignments}
          onStartEditPlan={() => setEditingPlan(true)}
        />
      )}

      <div className="plan-panel-header">
        <span className="plan-panel-title">Plan</span>
        <span className={`plan-panel-status plan-status-${plan.status}`}>
          {STATUS_LABEL[plan.status] ?? plan.status}
        </span>
        {userEditedBadge}
      </div>

      {provenanceCaption && (
        <div className="plan-provenance">{provenanceCaption}</div>
      )}

      <PipelineStepper stage={pipelineStage} planStatus={plan.status} />

      {plan.user_request && (
        <div className="plan-panel-prompt">
          <span className="plan-panel-prompt-label">Request</span>
          <div className="plan-panel-prompt-body">{plan.user_request}</div>
        </div>
      )}

      {/* Plan gate — markdown edit takes over the step list entirely */}
      {reviewState === "plan" && editingPlan ? (
        <PlanEditView
          draft={planDraft}
          onChange={setPlanDraft}
          onSave={() => onEditPlan(planDraft)}
          onCancel={() => {
            setEditingPlan(false);
            setPlanDraft(markdown);
          }}
        />
      ) : (
        <StepList
          steps={plan.steps}
          reviewState={reviewState}
          agents={agents}
          assignmentDrafts={assignmentDrafts}
          onChangeAssignment={(stepId, agentId) =>
            setAssignmentDrafts((d) => ({ ...d, [stepId]: agentId || null }))
          }
        />
      )}

      {/* Review action bar */}
      {reviewState === "plan" && !editingPlan && (
        <ReviewActions
          gate="plan"
          onApprove={onApprovePlan}
          onEdit={() => setEditingPlan(true)}
          feedback={planFeedback}
          onFeedbackChange={setPlanFeedbackText}
          onSendFeedback={() => {
            if (planFeedback.trim()) {
              onPlanFeedback(planFeedback.trim());
              setPlanFeedbackText("");
            }
          }}
          onCancel={onCancelRun}
        />
      )}

      {reviewState === "assignment" && (
        <ReviewActions
          gate="assignment"
          onApprove={onApproveAssignments}
          onEdit={() => {
            const updated = updateAssignmentsInMarkdown(
              markdown,
              plan,
              assignmentDrafts,
            );
            onEditAssignments(updated);
          }}
          editLabel="Save assignments"
          feedback={assignmentsFeedback}
          onFeedbackChange={setAssignmentsFeedbackText}
          onSendFeedback={() => {
            if (assignmentsFeedback.trim()) {
              onAssignmentsFeedback(assignmentsFeedback.trim());
              setAssignmentsFeedbackText("");
            }
          }}
          onCancel={onCancelRun}
        />
      )}

      <div className="plan-panel-footer">
        <button
          type="button"
          className="plan-panel-source-toggle"
          onClick={() => setShowSource((v) => !v)}
        >
          {showSource ? "hide markdown source" : "view markdown source"}
        </button>
      </div>

      {showSource && <pre className="plan-panel-source">{markdown}</pre>}
    </div>
  );
}

// =====================================================================
// Sub-components
// =====================================================================

interface PipelineStepperProps {
  stage: PipelineStage | null;
  planStatus: string;
}

/**
 * Horizontal 5-stage pipeline indicator: Planner → Recruiter → Manager →
 * Evaluator → Reporter. Stages before the active one are marked "done",
 * the active one is highlighted, later stages are dim.
 */
function PipelineStepper({ stage, planStatus }: PipelineStepperProps) {
  // "done" plan status visually marks all stages complete.
  const done = planStatus === "done";
  const activeIndex = stage ? PIPELINE_STAGES.indexOf(stage) : -1;

  return (
    <ol className="pipeline-stepper" aria-label="Pipeline progress">
      {PIPELINE_STAGES.map((s, i) => {
        let cls = "pipeline-step";
        if (done) {
          cls += " pipeline-step-done";
        } else if (activeIndex === -1) {
          cls += " pipeline-step-pending";
        } else if (i < activeIndex) {
          cls += " pipeline-step-done";
        } else if (i === activeIndex) {
          cls += " pipeline-step-active";
        } else {
          cls += " pipeline-step-pending";
        }
        return (
          <li key={s} className={cls} title={STAGE_LABELS[s]}>
            <span className="pipeline-step-dot" aria-hidden="true" />
            <span className="pipeline-step-label">{STAGE_LABELS[s]}</span>
          </li>
        );
      })}
    </ol>
  );
}

interface ReviewBannerProps {
  reviewState: Exclude<ReviewState, null>;
  editingPlan: boolean;
  onApprovePlan: () => void;
  onApproveAssignments: () => void;
  onStartEditPlan: () => void;
}

/**
 * Sticky high-visibility banner pinned to the top of the panel when a
 * copilot review gate is open. The primary action (Approve) is the most
 * prominent button. The full review action bar (Edit, Feedback, Cancel)
 * still lives below the step list so the user can pick a non-primary
 * action without losing the textarea / dropdowns.
 */
function ReviewBanner({
  reviewState,
  editingPlan,
  onApprovePlan,
  onApproveAssignments,
  onStartEditPlan,
}: ReviewBannerProps) {
  const headline =
    reviewState === "plan"
      ? "Your review is needed"
      : "Confirm agent assignments";
  const subline =
    reviewState === "plan"
      ? "The planner drafted a plan. Approve to continue, or edit/give feedback below."
      : "The recruiter chose an agent for each step. Approve to start execution, or change picks below.";
  const onPrimary =
    reviewState === "plan" ? onApprovePlan : onApproveAssignments;
  const primaryLabel =
    reviewState === "plan" ? "Approve plan" : "Approve assignments";

  return (
    <div className="plan-review-banner" role="alert">
      <div className="plan-review-banner-text">
        <strong>{headline}</strong>
        <span>{subline}</span>
      </div>
      <div className="plan-review-banner-actions">
        <button
          type="button"
          className="plan-action-btn primary"
          onClick={onPrimary}
        >
          {primaryLabel}
        </button>
        {reviewState === "plan" && !editingPlan && (
          <button
            type="button"
            className="plan-action-btn"
            onClick={onStartEditPlan}
          >
            Edit plan
          </button>
        )}
      </div>
    </div>
  );
}

interface StepListProps {
  steps: PlanStep[];
  reviewState: ReviewState;
  agents: AgentInfo[];
  assignmentDrafts: Record<number, string | null>;
  onChangeAssignment: (stepId: number, agentId: string) => void;
}

function StepList({
  steps,
  reviewState,
  agents,
  assignmentDrafts,
  onChangeAssignment,
}: StepListProps) {
  const isAssignmentReview = reviewState === "assignment";

  return (
    <ol className="plan-step-list">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`plan-step plan-step-status-${step.status}`}
        >
          <div className="plan-step-head">
            <span className="plan-step-num">Step {step.id}</span>
            <span className="plan-step-title">{step.title}</span>
            <span className={`plan-step-badge plan-status-${step.status}`}>
              {step.status}
            </span>
          </div>

          {step.description && (
            <div className="plan-step-field">
              <span className="plan-step-field-label">Description</span>
              <div>{step.description}</div>
            </div>
          )}

          {step.reasoning && (
            <div className="plan-step-field">
              <span className="plan-step-field-label">Reasoning</span>
              <div>{step.reasoning}</div>
            </div>
          )}

          {step.expected_artifacts.length > 0 && (
            <div className="plan-step-field">
              <span className="plan-step-field-label">Expected artifacts</span>
              <ul className="plan-step-artifacts">
                {step.expected_artifacts.map((a) => (
                  <li key={a}>
                    <code>{a}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Assignment view: dropdown when reviewing; otherwise plain text */}
          {isAssignmentReview ? (
            <div className="plan-step-field plan-step-assignment">
              <span className="plan-step-field-label">Assigned</span>
              <select
                className="plan-step-agent-select"
                value={assignmentDrafts[step.id] ?? ""}
                onChange={(e) =>
                  onChangeAssignment(step.id, e.target.value)
                }
              >
                <option value="" disabled>
                  -- choose agent --
                </option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
              {step.assignment_rationale && (
                <div className="plan-step-rationale">
                  {step.assignment_rationale}
                </div>
              )}
            </div>
          ) : (
            step.assigned_agent && (
              <div className="plan-step-field plan-step-assignment">
                <span className="plan-step-field-label">Assigned</span>
                <div>
                  <span className="plan-step-agent">
                    {step.assigned_agent}
                  </span>
                  {step.assignment_rationale && (
                    <span className="plan-step-rationale">
                      {" "}
                      — {step.assignment_rationale}
                    </span>
                  )}
                </div>
              </div>
            )
          )}

          {step.actual_outputs.length > 0 && (
            <div className="plan-step-field">
              <span className="plan-step-field-label">Outputs</span>
              <ul className="plan-step-artifacts">
                {step.actual_outputs.map((a) => (
                  <li key={a}>
                    <code>{a}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {step.params && Object.keys(step.params).length > 0 && (
            <details className="plan-step-params">
              <summary>
                Parameters ({Object.keys(step.params).length})
              </summary>
              <pre>{JSON.stringify(step.params, null, 2)}</pre>
            </details>
          )}
        </li>
      ))}
    </ol>
  );
}

interface PlanEditViewProps {
  draft: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

function PlanEditView({ draft, onChange, onSave, onCancel }: PlanEditViewProps) {
  return (
    <div className="plan-edit-view">
      <div className="plan-edit-help">
        Edit the plan markdown directly. Keep the <code>## Step N — Title</code>{" "}
        headings and the YAML fences. The server re-validates on save.
      </div>
      <textarea
        className="plan-edit-textarea"
        value={draft}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        rows={Math.min(28, Math.max(12, draft.split("\n").length + 1))}
      />
      <div className="plan-edit-actions">
        <button
          type="button"
          className="plan-action-btn primary"
          onClick={onSave}
        >
          Save & resume
        </button>
        <button type="button" className="plan-action-btn" onClick={onCancel}>
          Discard
        </button>
      </div>
    </div>
  );
}

interface ReviewActionsProps {
  gate: "plan" | "assignment";
  onApprove: () => void;
  onEdit?: () => void;
  editLabel?: string;
  feedback: string;
  onFeedbackChange: (v: string) => void;
  onSendFeedback: () => void;
  onCancel: () => void;
}

function ReviewActions({
  gate,
  onApprove,
  onEdit,
  editLabel,
  feedback,
  onFeedbackChange,
  onSendFeedback,
  onCancel,
}: ReviewActionsProps) {
  const approveLabel =
    gate === "plan" ? "Approve plan" : "Approve assignments";

  return (
    <div className="plan-review-bar">
      <div className="plan-review-buttons">
        <button
          type="button"
          className="plan-action-btn primary"
          onClick={onApprove}
        >
          {approveLabel}
        </button>
        {onEdit && (
          <button type="button" className="plan-action-btn" onClick={onEdit}>
            {editLabel ?? "Edit"}
          </button>
        )}
        <button type="button" className="plan-action-btn danger" onClick={onCancel}>
          Cancel run
        </button>
      </div>
      <div className="plan-review-feedback">
        <textarea
          className="plan-review-feedback-input"
          placeholder={
            gate === "plan"
              ? "Feedback to the planner (triggers a replan)…"
              : "Feedback to the planner about agent choice…"
          }
          value={feedback}
          onChange={(e) => onFeedbackChange(e.target.value)}
          rows={2}
        />
        <button
          type="button"
          className="plan-action-btn"
          onClick={onSendFeedback}
          disabled={!feedback.trim()}
        >
          Send feedback
        </button>
      </div>
    </div>
  );
}

// =====================================================================
// Helpers
// =====================================================================

/**
 * Build a fresh plan markdown string with updated ``assigned_agent``
 * values, mirroring ``PlanDocument.to_markdown`` in ``plan_store.py``.
 *
 * Only the assigned-agent values change — everything else is preserved
 * from the current ``plan`` object. The on-server ``apply_user_edit``
 * still re-validates the result.
 */
function updateAssignmentsInMarkdown(
  _currentMarkdown: string,
  plan: Plan,
  drafts: Record<number, string | null>,
): string {
  const yaml = (obj: Record<string, unknown>): string => {
    // Tiny YAML emitter that handles strings, nulls, and lists of strings —
    // matches what the backend's yaml.safe_dump produces for our payloads.
    const lines: string[] = [];
    for (const [k, v] of Object.entries(obj)) {
      if (v === null || v === undefined) {
        lines.push(`${k}: null`);
      } else if (Array.isArray(v)) {
        if (v.length === 0) lines.push(`${k}: []`);
        else {
          lines.push(`${k}:`);
          for (const item of v) lines.push(`- ${yamlScalar(String(item))}`);
        }
      } else {
        lines.push(`${k}: ${yamlScalar(String(v))}`);
      }
    }
    return lines.join("\n");
  };

  const out: string[] = ["# Plan", ""];
  const header: Record<string, unknown> = {
    status: plan.status,
    user_request: plan.user_request.trim(),
  };
  if (plan.last_edited_by) header.last_edited_by = plan.last_edited_by;
  if (plan.last_edited_at) header.last_edited_at = plan.last_edited_at;
  out.push("```yaml", yaml(header), "```", "");

  for (const step of plan.steps) {
    const assigned = drafts[step.id] ?? step.assigned_agent;
    out.push(`## Step ${step.id} — ${step.title}`, "");
    out.push(
      "```yaml",
      yaml({
        status: step.status,
        assigned_agent: assigned,
        assigned_rationale: step.assignment_rationale,
        expected_artifacts: step.expected_artifacts,
        actual_outputs: step.actual_outputs,
      }),
      "```",
    );
    if (step.description) out.push("", `**Description:** ${step.description}`);
    if (step.reasoning) out.push("", `**Reasoning:** ${step.reasoning}`);
    out.push("");
  }
  return out.join("\n").replace(/\n+$/, "") + "\n";
}

/** Quote a YAML scalar if it might be ambiguous; otherwise emit bare. */
function yamlScalar(s: string): string {
  if (s === "") return '""';
  if (/^[A-Za-z_][A-Za-z0-9_./-]*$/.test(s) && !["null", "true", "false", "yes", "no"].includes(s.toLowerCase())) {
    return s;
  }
  // Quote and escape backslash + double-quote.
  return `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

