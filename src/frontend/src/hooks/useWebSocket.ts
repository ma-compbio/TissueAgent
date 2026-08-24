import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AssignmentsApprovedEvent,
  AssignmentsEditedEvent,
  AssignmentsFeedbackEvent,
  HistoryData,
  MetricsData,
  PlanApprovedEvent,
  PlanEditedEvent,
  PlanFeedbackEvent,
  RunCancelledClientEvent,
  SendMessageEvent,
  SerializedMessage,
  ServerEvent,
  SessionMode,
  SetModeEvent,
  SubagentTranscript,
} from "../types/messages";

interface PlanUpdatePayload {
  markdown: string;
  plan: unknown; // PlanPayload-shaped; consumers cast to the real type.
}

/** Auto-save fired on the server. The frontend consumes this to refresh
 *  the Projects list and highlight the active project. */
export interface ProjectSavedPayload {
  project_id: string;
  title: string;
}

/** Which copilot review gate is open. ``null`` ⇒ no review pending. */
export type ReviewState = "plan" | "assignment" | null;

/** Three-state connection status. ``connecting`` covers both the
 *  initial WebSocket handshake and any in-flight auto-reconnect — both
 *  of which produce a flicker of ``onerror`` / ``onclose`` events that
 *  shouldn't be shown to the user as a hard error. */
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/** Identifiers of the five main pipeline agents, in execution order. */
export type PipelineStage =
  | "planner"
  | "recruiter"
  | "manager"
  | "evaluator"
  | "reporter";

export const PIPELINE_STAGES: PipelineStage[] = [
  "planner",
  "recruiter",
  "manager",
  "evaluator",
  "reporter",
];

const _AGENT_NAME_TO_STAGE: Record<string, PipelineStage> = {
  planner_agent: "planner",
  recruiter_agent: "recruiter",
  manager_agent: "manager",
  evaluator_agent: "evaluator",
  reporter_agent: "reporter",
};

interface UseWebSocketReturn {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  liveTraces: Record<string, SubagentTranscript>;
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
  isRunning: boolean;
  elapsed: number | null;
  error: string | null;
  planEvent: PlanUpdatePayload | null;
  /** Last project_saved event from the server. Bumps every save so the
   *  consumer can use it as a refetch signal. */
  projectSavedEvent: ProjectSavedPayload | null;
  mode: SessionMode;
  setMode: (mode: SessionMode) => void;
  sendMessage: (text: string, imageIds?: string[], pdfIds?: string[]) => void;
  clearError: () => void;
  reviewState: ReviewState;
  /** Most recent pipeline stage observed in the message stream, or null. */
  pipelineStage: PipelineStage | null;
  /** Latest API usage snapshot from the server, or null before the first event. */
  metrics: MetricsData | null;
  approvePlan: () => void;
  editPlan: (markdown: string) => void;
  sendPlanFeedback: (text: string) => void;
  approveAssignments: () => void;
  editAssignments: (markdown: string) => void;
  sendAssignmentsFeedback: (text: string) => void;
  cancelRun: () => void;
  /** Force a reconnect so the server re-sends history + mode. Used after a
   *  session load so the frontend picks up the restored state in place,
   *  without a hard ``window.location.reload``. */
  reconnect: () => void;
}

const WS_URL =
  import.meta.env.DEV
    ? `ws://${window.location.hostname}:8000/ws/chat`
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/chat`;

// The transcript array only ever grows during a session; every message also
// becomes live DOM in ChatView. Left unbounded, a long run drives the
// QtWebEngine renderer to OOM (SIGTRAP). Keep only the most recent messages —
// older turns scroll out of view and aren't worth the memory. The full
// transcript is still persisted server-side and replayable via history.
const MAX_MESSAGES = 1500;

/** Keep the last MAX_MESSAGES entries, returning the same array if under cap. */
function capMessages(msgs: SerializedMessage[]): SerializedMessage[] {
  return msgs.length > MAX_MESSAGES ? msgs.slice(-MAX_MESSAGES) : msgs;
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // Buffers messages the caller tried to send while the socket was closed or
  // still opening. Flushed on onopen. Prevents the "prompt disappears with
  // just a toast" bug when send() races the initial handshake.
  const sendQueue = useRef<string[]>([]);

  const [messages, setMessages] = useState<SerializedMessage[]>([]);
  const [subagentStates, setSubagentStates] = useState<
    Record<string, SubagentTranscript>
  >({});
  const [liveTraces, setLiveTraces] = useState<
    Record<string, SubagentTranscript>
  >({});
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [isRunning, setIsRunning] = useState(false);
  const disconnectEscalation = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planEvent, setPlanEvent] = useState<PlanUpdatePayload | null>(null);
  const [projectSavedEvent, setProjectSavedEvent] =
    useState<ProjectSavedPayload | null>(null);
  const [mode, setModeState] = useState<SessionMode>("autopilot");
  const [reviewState, setReviewState] = useState<ReviewState>(null);
  const [metrics, setMetrics] = useState<MetricsData | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    // Until we either open or definitively give up, we're "connecting".
    setConnectionStatus("connecting");

    ws.onopen = () => {
      setIsConnected(true);
      setConnectionStatus("connected");
      // Clear any stale error from a previous lost connection.
      setError(null);
      // A pending reconnect timer would race with the freshly-opened
      // socket and could open a duplicate; drop it now.
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
      clearTimeout(disconnectEscalation.current);
      disconnectEscalation.current = undefined;
      // Flush anything the caller tried to send before the handshake
      // finished (React strict mode + slow servers make this common).
      if (sendQueue.current.length > 0) {
        const queued = sendQueue.current;
        sendQueue.current = [];
        for (const payload of queued) {
          try {
            ws.send(payload);
          } catch {
            // If a queued flush fails, put it back so the next reconnect
            // gets a shot at it. Rare — but silently dropping user input is
            // worse than a small buffer churn.
            sendQueue.current.push(payload);
          }
        }
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Stay in "connecting" while the auto-reconnect (2s below) does
      // its thing — the user shouldn't see a hard "Disconnected" state
      // during a brief blip. Escalate to "disconnected" only if we
      // haven't reconnected within a longer grace window.
      setConnectionStatus("connecting");
      clearTimeout(disconnectEscalation.current);
      disconnectEscalation.current = setTimeout(() => {
        setConnectionStatus("disconnected");
      }, 6000);
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    /* onerror always fires together with onclose for connect-time
       failures. We don't surface its message — it's the browser's
       generic "WebSocket connection error" and reads as if something
       is actually wrong, when in practice it just means "the server
       isn't up yet" or "I'm still reconnecting". The connection-status
       badge tells the user whether we're connecting or disconnected. */
    ws.onerror = () => {
      // Intentional no-op for user-facing state. The onclose handler
      // owns the lifecycle.
    };

    ws.onmessage = (event) => {
      let data: ServerEvent;
      try {
        data = JSON.parse(event.data);
      } catch (err) {
        // A single malformed frame must not tear down the socket — that
        // would leave the whole session unreachable until the user
        // reloads. Log and drop instead.
        // eslint-disable-next-line no-console
        console.warn("Ignoring malformed WebSocket frame", err);
        return;
      }

      switch (data.type) {
        case "history": {
          const history = data.data as HistoryData;
          setMessages(capMessages(history.messages));
          setSubagentStates(history.subagent_states);
          setLiveTraces({});
          // A history replay is definitionally a fresh page-load view of
          // the transcript — any in-flight run indicator is stale.
          setIsRunning(false);
          setElapsed(null);
          break;
        }
        case "message": {
          const msg = data.data as SerializedMessage;
          setMessages((prev) => capMessages([...prev, msg]));
          if (msg.type === "human") {
            setIsRunning(true);
            setElapsed(null);
          }
          break;
        }
        case "subagent_start": {
          const { invocation_id, agent_name, avatar } = data.data;
          setLiveTraces((prev) => ({
            ...prev,
            [invocation_id]: {
              tool_id: invocation_id,
              agent_name,
              avatar,
              transcript: [],
              raw_state: null,
              invocation_id,
            },
          }));
          break;
        }
        case "subagent_message": {
          const { invocation_id, message: msg } = data.data;
          setLiveTraces((prev) => {
            const existing = prev[invocation_id];
            if (!existing) return prev;
            return {
              ...prev,
              [invocation_id]: {
                ...existing,
                transcript: [...(existing.transcript || []), msg],
              },
            };
          });
          break;
        }
        case "subagent_end": {
          // Keep the live trace until subagent_state arrives with the final transcript
          break;
        }
        case "subagent_state": {
          const state = data.data as SubagentTranscript;
          if (state.tool_id !== "pending") {
            setSubagentStates((prev) => {
              const next = { ...prev, [state.tool_id]: state };
              // Also index by invocation_id so selectedTrace survives the transition
              if (state.invocation_id) {
                next[state.invocation_id] = state;
              }
              return next;
            });
            // Remove from live traces
            if (state.invocation_id) {
              setLiveTraces((prev) => {
                const next = { ...prev };
                delete next[state.invocation_id!];
                return next;
              });
            }
          }
          break;
        }
        case "run_complete":
          setIsRunning(false);
          setElapsed(data.elapsed_seconds);
          setLiveTraces({});
          setReviewState(null);
          break;
        case "run_error":
          setIsRunning(false);
          setError(`${data.error_type}: ${data.detail}`);
          setLiveTraces({});
          // Note: don't clear reviewState on errors that come *during* a
          // review (e.g. PlanEditError). Only clear it on terminal errors
          // — for simplicity we leave it set; the user can retry or cancel.
          break;
        case "plan_updated":
          setPlanEvent(data.data as PlanUpdatePayload);
          break;
        case "mode_updated":
          setModeState(data.data.mode);
          break;
        case "plan_review_requested":
          setReviewState("plan");
          break;
        case "assignment_review_requested":
          setReviewState("assignment");
          break;
        case "run_cancelled":
          setIsRunning(false);
          setLiveTraces({});
          setReviewState(null);
          break;
        case "project_saved":
          setProjectSavedEvent(data.data);
          break;
        case "metrics_updated":
          setMetrics(data.data);
          break;
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearTimeout(disconnectEscalation.current);
      const sock = wsRef.current;
      wsRef.current = null;
      if (sock) {
        // Detach handlers BEFORE close — otherwise onclose fires after
        // unmount and schedules another 2s reconnect that then opens a
        // socket into a dead component (React strict mode makes this
        // trivially reproducible in dev).
        sock.onopen = null;
        sock.onmessage = null;
        sock.onerror = null;
        sock.onclose = null;
        try {
          sock.close();
        } catch {
          // best-effort cleanup
        }
      }
    };
  }, [connect]);

  const send = useCallback((payload: object) => {
    const serialised = JSON.stringify(payload);
    const sock = wsRef.current;
    if (sock && sock.readyState === WebSocket.OPEN) {
      sock.send(serialised);
      return;
    }
    // CONNECTING (initial handshake, reconnect) → queue and flush on
    // open. CLOSING/CLOSED → also queue; the auto-reconnect will drain
    // it. This turns a "prompt vanished with only a toast" into a
    // slight, honest delay.
    sendQueue.current.push(serialised);
    if (!sock || sock.readyState === WebSocket.CLOSED) {
      // Nudge the reconnect if we're fully closed — the timer might not
      // be scheduled if this send happened outside the close path.
      if (!reconnectTimer.current) {
        reconnectTimer.current = setTimeout(connect, 100);
      }
    }
  }, [connect]);

  const sendMessage = useCallback(
    (text: string, imageIds: string[] = [], pdfIds: string[] = []) => {
      const event: SendMessageEvent = {
        type: "send_message",
        text,
        image_ids: imageIds,
        pdf_ids: pdfIds,
      };
      send(event);
    },
    [send]
  );

  const setMode = useCallback(
    (next: SessionMode) => {
      const event: SetModeEvent = { type: "set_mode", mode: next };
      send(event);
    },
    [send]
  );

  // ---- copilot review actions --------------------------------------
  // Each action optimistically clears ``reviewState`` so the review
  // banner disappears the moment the user clicks — it has done its
  // job. If the server pauses again later (e.g. at the next gate, or
  // after a feedback-triggered replan), a fresh ``*_review_requested``
  // event will set ``reviewState`` again.

  const approvePlan = useCallback(() => {
    setReviewState(null);
    const event: PlanApprovedEvent = { type: "plan_approved" };
    send(event);
  }, [send]);

  const editPlan = useCallback(
    (markdown: string) => {
      setReviewState(null);
      const event: PlanEditedEvent = { type: "plan_edited", markdown };
      send(event);
    },
    [send]
  );

  const sendPlanFeedback = useCallback(
    (text: string) => {
      setReviewState(null);
      const event: PlanFeedbackEvent = { type: "plan_feedback", text };
      send(event);
    },
    [send]
  );

  const approveAssignments = useCallback(() => {
    setReviewState(null);
    const event: AssignmentsApprovedEvent = { type: "assignments_approved" };
    send(event);
  }, [send]);

  const editAssignments = useCallback(
    (markdown: string) => {
      setReviewState(null);
      const event: AssignmentsEditedEvent = { type: "assignments_edited", markdown };
      send(event);
    },
    [send]
  );

  const sendAssignmentsFeedback = useCallback(
    (text: string) => {
      setReviewState(null);
      const event: AssignmentsFeedbackEvent = { type: "assignments_feedback", text };
      send(event);
    },
    [send]
  );

  const cancelRun = useCallback(() => {
    setReviewState(null);
    const event: RunCancelledClientEvent = { type: "run_cancelled" };
    send(event);
  }, [send]);

  const reconnect = useCallback(() => {
    // Cancel any pending auto-reconnect, drop the current socket, and
    // immediately re-open. The fresh socket fires the normal ``history``
    // and ``mode_updated`` payloads from the server.
    clearTimeout(reconnectTimer.current);
    reconnectTimer.current = undefined;
    clearTimeout(disconnectEscalation.current);
    disconnectEscalation.current = undefined;
    if (wsRef.current) {
      // Detach handlers so the close doesn't schedule a 2s auto-reconnect.
      const sock = wsRef.current;
      sock.onclose = null;
      sock.onerror = null;
      try {
        sock.close();
      } catch {
        // Ignore; we're about to open a new socket.
      }
      wsRef.current = null;
    }
    connect();
  }, [connect]);

  const clearError = useCallback(() => setError(null), []);

  // Pipeline stage is derived from the most recent main-agent message in
  // the chat stream. We look only at the tail because messages from the
  // earlier stages stay in history forever and would otherwise pin the
  // stepper to "planner" indefinitely.
  const pipelineStage = useMemo<PipelineStage | null>(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const name = messages[i]?.name ?? "";
      const stage = _AGENT_NAME_TO_STAGE[name];
      if (stage) return stage;
    }
    return null;
  }, [messages]);

  return {
    messages,
    subagentStates,
    liveTraces,
    isConnected,
    connectionStatus,
    isRunning,
    elapsed,
    error,
    planEvent,
    projectSavedEvent,
    mode,
    setMode,
    sendMessage,
    clearError,
    reviewState,
    pipelineStage,
    metrics,
    approvePlan,
    editPlan,
    sendPlanFeedback,
    approveAssignments,
    editAssignments,
    sendAssignmentsFeedback,
    cancelRun,
    reconnect,
  };
}
