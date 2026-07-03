/** TypeScript types matching the backend message serialization format. */

export interface ToolCall {
  id: string | null;
  name: string;
  args: Record<string, unknown>;
}

export interface SerializedMessage {
  id: string | null;
  type: "human" | "ai" | "tool";
  name: string | null;
  content: string;
  avatar: string;
  label?: string;

  // AI message fields
  route?: string | null;
  body?: string;
  tags?: Record<string, string> | null;
  tool_calls?: ToolCall[];

  // Tool message fields
  tool_call_id?: string | null;
  status?: string | null;
}

export interface SubagentTranscript {
  tool_id: string;
  agent_name: string;
  avatar: string;
  transcript: SerializedMessage[] | null;
  raw_state: string | null;
  invocation_id?: string | null;
}

export interface HistoryData {
  messages: SerializedMessage[];
  subagent_states: Record<string, SubagentTranscript>;
}

/** Execution mode. Autopilot runs end-to-end; copilot pauses for human
 *  review after the planner and after the recruiter. */
export type SessionMode = "autopilot" | "copilot";

/** Copilot pause labels — must match server-side `_interrupt_label`. */
export type PauseLabel = "before_recruiter" | "before_manager";

/** Per-agent accumulated API usage across the session. Mirrors
 *  ``server.usage_tracker.AgentMetrics``. */
export interface AgentMetrics {
  input_tokens: number;
  output_tokens: number;
  time_seconds: number;
  llm_calls: number;
}

/** Per-plan-step accumulated API usage. Mirrors
 *  ``server.usage_tracker.StepMetrics``. */
export interface StepMetrics extends AgentMetrics {
  step_id: number;
  agent_name: string;
}

/** Full snapshot of the session's API usage. */
export interface MetricsData {
  agents: Record<string, AgentMetrics>;
  steps: StepMetrics[];
}

/** WebSocket event types from server. */
export type ServerEvent =
  | { type: "history"; data: HistoryData }
  | { type: "message"; data: SerializedMessage }
  | { type: "subagent_state"; data: SubagentTranscript }
  | { type: "subagent_start"; data: { invocation_id: string; agent_name: string; avatar: string } }
  | { type: "subagent_message"; data: { invocation_id: string; agent_name: string; message: SerializedMessage } }
  | { type: "subagent_end"; data: { invocation_id: string; agent_name: string } }
  | { type: "run_complete"; elapsed_seconds: number }
  | { type: "run_error"; error_type: string; detail: string }
  | { type: "plan_updated"; data: { markdown: string; plan: unknown } }
  | { type: "mode_updated"; data: { mode: SessionMode } }
  | { type: "plan_review_requested"; data: { pause: PauseLabel } }
  | { type: "assignment_review_requested"; data: { pause: PauseLabel } }
  | { type: "run_cancelled"; data: Record<string, never> }
  | { type: "project_saved"; data: { project_id: string; title: string } }
  | { type: "metrics_updated"; data: MetricsData };

/** WebSocket event types from client. */
export interface SendMessageEvent {
  type: "send_message";
  text: string;
  image_ids: string[];
  pdf_ids: string[];
}

export interface SetModeEvent {
  type: "set_mode";
  mode: SessionMode;
}

/** Approve the currently-paused plan as-is. */
export interface PlanApprovedEvent {
  type: "plan_approved";
}

/** Submit edited plan markdown; server validates + persists + resumes. */
export interface PlanEditedEvent {
  type: "plan_edited";
  markdown: string;
}

/** Submit free-text feedback on the plan; rewinds to the planner. */
export interface PlanFeedbackEvent {
  type: "plan_feedback";
  text: string;
}

export interface AssignmentsApprovedEvent {
  type: "assignments_approved";
}

export interface AssignmentsEditedEvent {
  type: "assignments_edited";
  markdown: string;
}

export interface AssignmentsFeedbackEvent {
  type: "assignments_feedback";
  text: string;
}

export interface RunCancelledClientEvent {
  type: "run_cancelled";
}

export interface FileInfo {
  name: string;
  path: string;
  category?: string;
  file_id?: string | null;
}

export interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  children?: BrowseEntry[] | null;
}

export interface SessionInfo {
  filename: string;
  label: string;
  path: string;
  /** First user message, derived at save time. Empty for legacy sessions. */
  title?: string;
  /** Stable on-disk filename stem; doubles as project id. */
  project_id?: string;
  /** Last-modified time as displayed in the projects list. */
  saved_at?: string;
}
