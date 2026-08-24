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

  // Coding-agent plot references: project-relative paths (e.g.
  // "outputs/figures/_trace/<id>.png") loaded from the file-download API.
  image_paths?: string[];
}

export interface SubagentTranscript {
  tool_id: string;
  agent_name: string;
  avatar: string;
  transcript: SerializedMessage[] | null;
  /** Kebab-case names of the skills loaded into this step's sub-agent.
   *  Populated from the plan step's assigned skills; empty for steps that
   *  loaded none, and absent on legacy sessions saved before this existed. */
  skills?: string[];
  /** Fully-rendered system prompt the sub-agent ran with (skills already
   *  substituted). Absent on legacy sessions saved before this existed. */
  system_prompt?: string | null;
  raw_state: string | null;
  invocation_id?: string | null;
}

/** Detail for a single skill, fetched lazily from `/api/skills/{name}`. */
export interface SkillDetail {
  name: string;
  description: string;
  applies_to: string[];
  /** True for folder-based skills that ship bundled scripts/ + references/. */
  is_dir: boolean;
  /** Full markdown body of the skill's own file. */
  content: string;
  /** Repo-relative folder path, e.g. "knowledge/skills/figure-reproduce".
   *  Only present for folder skills. */
  dir_path?: string;
  /** Skill markdown filename within the folder (e.g. "figure-reproduce.md"). */
  main_file?: string;
  /** File tree under the skill folder, paths relative to it. Folder skills only. */
  files?: BrowseEntry[];
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
