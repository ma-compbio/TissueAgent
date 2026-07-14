import { useCallback, useEffect, useRef, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export type PlanStatus =
  | "empty"
  | "draft"
  | "awaiting_plan_review"
  | "recruited"
  | "awaiting_assignment_review"
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
  /** Args the manager passed to the specialist for this step. Populated
   *  post-hoc on save / export; absent at planning time. */
  params?: Record<string, unknown> | null;
}

export type EditedBy = "planner" | "recruiter" | "manager" | "user";

export interface PlanProvenance {
  template_names: string[];
  decision?: string | null;
}

export interface Plan {
  status: PlanStatus;
  user_request: string;
  steps: PlanStep[];
  last_edited_by?: EditedBy | null;
  last_edited_at?: string | null;
  provenance?: PlanProvenance | null;
}

export interface PlanPayload {
  markdown: string;
  plan: Plan;
}

const EMPTY_PLAN: Plan = {
  status: "empty",
  user_request: "",
  steps: [],
  last_edited_by: null,
  last_edited_at: null,
  provenance: null,
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
  // Monotonic request token. A completed fetch only applies its result
  // when it is still the newest outstanding one, so a stale mount-fetch
  // can't clobber a fresh plan_updated event that landed first.
  const latestReqRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    const token = ++latestReqRef.current;
    fetch(`${API}/api/plan`)
      .then((r) => (r.ok ? (r.json() as Promise<PlanPayload>) : null))
      .then((data) => {
        if (!mountedRef.current || !data) return;
        if (token !== latestReqRef.current) return; // superseded
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
    // WebSocket events are the freshest source of truth. Bump the token
    // so any in-flight fetch that finishes later can't overwrite this.
    latestReqRef.current += 1;
    setPlan(payload.plan ?? EMPTY_PLAN);
    setMarkdown(payload.markdown ?? "");
  }, []);

  const clear = useCallback(() => {
    latestReqRef.current += 1;
    setPlan(EMPTY_PLAN);
    setMarkdown("");
  }, []);

  const refresh = useCallback(async () => {
    const token = ++latestReqRef.current;
    try {
      const res = await fetch(`${API}/api/plan`);
      if (!res.ok) return;
      const data = (await res.json()) as PlanPayload;
      if (!mountedRef.current || token !== latestReqRef.current) return;
      setPlan(data.plan ?? EMPTY_PLAN);
      setMarkdown(data.markdown ?? "");
    } catch {
      // Non-fatal — caller can retry.
    }
  }, []);

  return { plan, markdown, applyEvent, clear, refresh };
}
