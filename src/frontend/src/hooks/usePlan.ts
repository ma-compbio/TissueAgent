import { useCallback, useEffect, useRef, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export type PlanStatus =
  | "empty"
  | "draft"
  | "recruited"
  | "approved"
  | "running"
  | "paused"
  | "done"
  | "failed";

export type StepStatus =
  | "pending"
  | "running"
  | "done"
  | "skipped"
  | "failed";

export interface PlanStep {
  id: number;
  title: string;
  description: string;
  reasoning: string;
  expected_artifacts: string[];
  assigned_agent: string | null;
  assignment_rationale: string | null;
  status: StepStatus;
  actual_outputs: string[];
}

export interface Plan {
  status: PlanStatus;
  user_request: string;
  steps: PlanStep[];
}

export interface PlanPayload {
  markdown: string;
  plan: Plan;
}

const EMPTY_PLAN: Plan = {
  status: "empty",
  user_request: "",
  steps: [],
};

/**
 * Tracks the current plan as authored by the planner + recruiter.
 *
 * The plan is fetched once on mount and refreshed on every `plan_updated`
 * WebSocket event. The hook itself does not own the WebSocket — the
 * caller is responsible for forwarding events via `applyEvent`.
 */
export function usePlan() {
  const [plan, setPlan] = useState<Plan>(EMPTY_PLAN);
  const [markdown, setMarkdown] = useState<string>("");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    fetch(`${API}/api/plan`)
      .then((r) => (r.ok ? (r.json() as Promise<PlanPayload>) : null))
      .then((data) => {
        if (!mountedRef.current || !data) return;
        setPlan(data.plan ?? EMPTY_PLAN);
        setMarkdown(data.markdown ?? "");
      })
      .catch(() => {
        // Silently ignore — the plan is non-critical for first paint.
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const applyEvent = useCallback((payload: PlanPayload) => {
    setPlan(payload.plan ?? EMPTY_PLAN);
    setMarkdown(payload.markdown ?? "");
  }, []);

  const clear = useCallback(() => {
    setPlan(EMPTY_PLAN);
    setMarkdown("");
  }, []);

  return { plan, markdown, applyEvent, clear };
}
