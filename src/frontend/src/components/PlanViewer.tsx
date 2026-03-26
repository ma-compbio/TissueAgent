import { useState } from "react";
import type { SerializedMessage } from "../types/messages";

export interface PlanEntry {
  id: string;
  agentName: string;
  avatar: string;
  label: string;
  title: string;
  details: string;
}

interface Props {
  prompt: string | null;
  entries: PlanEntry[];
  isRunning: boolean;
}

const MAIN_AGENT_NAMES = new Set([
  "planner_agent",
  "recruiter_agent",
  "manager_agent",
  "evaluator_agent",
  "reporter_agent",
]);

/** Pipeline display order for agents. */
const PIPELINE_ORDER = [
  "planner_agent",
  "recruiter_agent",
  "manager_agent",
  "evaluator_agent",
  "reporter_agent",
];

/** Labels that are too generic to use as titles. */
const SKIP_LABELS = new Set(["PLAN", "Steps:", "EVALUATION:", "FORWARDING:"]);

/** Pick the first meaningful line from the agent's body text. */
function extractTitle(body: string, route: string | null | undefined): string {
  const lines = body.split("\n").map((l) => l.trim()).filter((l) => l);
  for (const line of lines) {
    if (SKIP_LABELS.has(line)) continue;
    const candidate = line.length > 80 ? line.slice(0, 77) + "..." : line;
    if (candidate.length > 3) return candidate;
  }
  return route ? `Route: ${route}` : "Update";
}

/** Extract plan entries from the messages after the last human message.
 *
 *  Takes the last message from each main-pipeline agent (planner, recruiter,
 *  manager, evaluator, reporter) and shows them in pipeline order.
 */
export function extractPlanData(messages: SerializedMessage[]): {
  prompt: string | null;
  entries: PlanEntry[];
} {
  let lastHumanIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type === "human") {
      lastHumanIdx = i;
      break;
    }
  }

  if (lastHumanIdx === -1) return { prompt: null, entries: [] };

  const prompt = messages[lastHumanIdx].content;

  // Collect the last message from each main agent after the prompt
  const lastByAgent = new Map<string, { msg: SerializedMessage; idx: number }>();
  for (let i = lastHumanIdx + 1; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.type !== "ai" || !msg.name || !MAIN_AGENT_NAMES.has(msg.name))
      continue;
    const body = (msg.body || msg.content || "").trim();
    if (!body) continue;
    lastByAgent.set(msg.name, { msg, idx: i });
  }

  // Emit entries in pipeline order
  const entries: PlanEntry[] = [];
  for (const agentName of PIPELINE_ORDER) {
    const hit = lastByAgent.get(agentName);
    if (!hit) continue;
    const { msg, idx } = hit;
    const body = (msg.body || msg.content || "").trim();
    entries.push({
      id: msg.id || `plan-${idx}`,
      agentName: msg.name!,
      avatar: msg.avatar,
      label: msg.label || msg.name || "Agent",
      title: extractTitle(body, msg.route),
      details: body,
    });
  }

  return { prompt, entries };
}

export default function PlanViewer({ prompt, entries, isRunning }: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="plan-viewer">
      <div className="plan-viewer-header">Plan</div>

      {!prompt && entries.length === 0 && (
        <div className="plan-empty">
          No plan yet. Send a message to get started.
        </div>
      )}

      {prompt && <div className="plan-prompt">{prompt}</div>}

      <div className="plan-steps">
        {entries.map((entry) => {
          const isExpanded = expandedIds.has(entry.id);
          return (
            <div key={entry.id} className="plan-step">
              <button
                className="plan-step-header"
                onClick={() => toggleExpand(entry.id)}
              >
                <span className="plan-step-toggle">
                  {isExpanded ? "▼" : "▶"}
                </span>
                <span className="plan-step-avatar">{entry.avatar}</span>
                <span className="plan-step-label">{entry.label}</span>
                <span className="plan-step-title">{entry.title}</span>
              </button>
              {isExpanded && (
                <div className="plan-step-details">{entry.details}</div>
              )}
            </div>
          );
        })}

        {isRunning && entries.length > 0 && (
          <div className="plan-step-loading">
            <div className="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
