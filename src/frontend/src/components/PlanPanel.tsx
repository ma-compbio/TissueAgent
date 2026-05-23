/**
 * Read-only view of the evolving plan (phase 1).
 *
 * Renders the plan's structured fields per step. The raw markdown source
 * is available behind a "view source" toggle for debugging and for
 * users who'd rather copy the plan into their own editor.
 */

import { useState } from "react";
import type { Plan } from "../hooks/usePlan";

interface Props {
  plan: Plan;
  markdown: string;
}

const STATUS_LABEL: Record<string, string> = {
  empty: "no plan yet",
  draft: "draft — recruiter has not assigned agents",
  recruited: "ready — assignments complete",
  approved: "approved",
  running: "running",
  paused: "paused",
  done: "done",
  failed: "failed",
};

export default function PlanPanel({ plan, markdown }: Props) {
  const [showSource, setShowSource] = useState(false);

  if (plan.status === "empty" || plan.steps.length === 0) {
    return (
      <div className="plan-panel">
        <div className="plan-panel-header">
          <span className="plan-panel-title">Plan</span>
          <span className="plan-panel-status plan-status-empty">no plan yet</span>
        </div>
        <div className="plan-panel-empty">
          Send a message that needs analysis — the planner will draft a plan here.
        </div>
      </div>
    );
  }

  return (
    <div className="plan-panel">
      <div className="plan-panel-header">
        <span className="plan-panel-title">Plan</span>
        <span
          className={`plan-panel-status plan-status-${plan.status}`}
        >
          {STATUS_LABEL[plan.status] ?? plan.status}
        </span>
      </div>

      {plan.user_request && (
        <div className="plan-panel-prompt">
          <span className="plan-panel-prompt-label">Request</span>
          <div className="plan-panel-prompt-body">{plan.user_request}</div>
        </div>
      )}

      <ol className="plan-step-list">
        {plan.steps.map((step) => (
          <li key={step.id} className={`plan-step plan-step-status-${step.status}`}>
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

            {step.assigned_agent && (
              <div className="plan-step-field plan-step-assignment">
                <span className="plan-step-field-label">Assigned</span>
                <div>
                  <span className="plan-step-agent">{step.assigned_agent}</span>
                  {step.assignment_rationale && (
                    <span className="plan-step-rationale">
                      {" "}
                      — {step.assignment_rationale}
                    </span>
                  )}
                </div>
              </div>
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
          </li>
        ))}
      </ol>

      <div className="plan-panel-footer">
        <button
          type="button"
          className="plan-panel-source-toggle"
          onClick={() => setShowSource((v) => !v)}
        >
          {showSource ? "hide markdown source" : "view markdown source"}
        </button>
      </div>

      {showSource && (
        <pre className="plan-panel-source">{markdown}</pre>
      )}
    </div>
  );
}
