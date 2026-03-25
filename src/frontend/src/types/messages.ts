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
}

export interface HistoryData {
  messages: SerializedMessage[];
  subagent_states: Record<string, SubagentTranscript>;
}

/** WebSocket event types from server. */
export type ServerEvent =
  | { type: "history"; data: HistoryData }
  | { type: "message"; data: SerializedMessage }
  | { type: "subagent_state"; data: SubagentTranscript }
  | { type: "run_complete"; elapsed_seconds: number }
  | { type: "run_error"; error_type: string; detail: string };

/** WebSocket event types from client. */
export interface SendMessageEvent {
  type: "send_message";
  text: string;
  image_ids: string[];
  pdf_ids: string[];
}

export interface FileInfo {
  name: string;
  path: string;
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
}
