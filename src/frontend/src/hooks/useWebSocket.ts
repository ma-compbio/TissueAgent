import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AssignmentsApprovedEvent,
  AssignmentsEditedEvent,
  AssignmentsFeedbackEvent,
  HistoryData,
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

/** Which copilot review gate is open. ``null`` ⇒ no review pending. */
export type ReviewState = "plan" | "assignment" | null;

interface UseWebSocketReturn {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  liveTraces: Record<string, SubagentTranscript>;
  isConnected: boolean;
  isRunning: boolean;
  elapsed: number | null;
  error: string | null;
  planEvent: PlanUpdatePayload | null;
  mode: SessionMode;
  setMode: (mode: SessionMode) => void;
  sendMessage: (text: string, imageIds?: string[], pdfIds?: string[]) => void;
  clearError: () => void;
  reviewState: ReviewState;
  approvePlan: () => void;
  editPlan: (markdown: string) => void;
  sendPlanFeedback: (text: string) => void;
  approveAssignments: () => void;
  editAssignments: (markdown: string) => void;
  sendAssignmentsFeedback: (text: string) => void;
  cancelRun: () => void;
}

const WS_URL =
  import.meta.env.DEV
    ? `ws://${window.location.hostname}:8000/ws/chat`
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/chat`;

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const [messages, setMessages] = useState<SerializedMessage[]>([]);
  const [subagentStates, setSubagentStates] = useState<
    Record<string, SubagentTranscript>
  >({});
  const [liveTraces, setLiveTraces] = useState<
    Record<string, SubagentTranscript>
  >({});
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planEvent, setPlanEvent] = useState<PlanUpdatePayload | null>(null);
  const [mode, setModeState] = useState<SessionMode>("autopilot");
  const [reviewState, setReviewState] = useState<ReviewState>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Reconnect after 2 seconds
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };

    ws.onmessage = (event) => {
      const data: ServerEvent = JSON.parse(event.data);

      switch (data.type) {
        case "history": {
          const history = data.data as HistoryData;
          setMessages(history.messages);
          setSubagentStates(history.subagent_states);
          setLiveTraces({});
          break;
        }
        case "message": {
          const msg = data.data as SerializedMessage;
          setMessages((prev) => [...prev, msg]);
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
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((payload: object) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }
    wsRef.current.send(JSON.stringify(payload));
  }, []);

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

  // ---- copilot review actions ----

  const approvePlan = useCallback(() => {
    const event: PlanApprovedEvent = { type: "plan_approved" };
    send(event);
  }, [send]);

  const editPlan = useCallback(
    (markdown: string) => {
      const event: PlanEditedEvent = { type: "plan_edited", markdown };
      send(event);
    },
    [send]
  );

  const sendPlanFeedback = useCallback(
    (text: string) => {
      const event: PlanFeedbackEvent = { type: "plan_feedback", text };
      send(event);
    },
    [send]
  );

  const approveAssignments = useCallback(() => {
    const event: AssignmentsApprovedEvent = { type: "assignments_approved" };
    send(event);
  }, [send]);

  const editAssignments = useCallback(
    (markdown: string) => {
      const event: AssignmentsEditedEvent = { type: "assignments_edited", markdown };
      send(event);
    },
    [send]
  );

  const sendAssignmentsFeedback = useCallback(
    (text: string) => {
      const event: AssignmentsFeedbackEvent = { type: "assignments_feedback", text };
      send(event);
    },
    [send]
  );

  const cancelRun = useCallback(() => {
    const event: RunCancelledClientEvent = { type: "run_cancelled" };
    send(event);
  }, [send]);

  const clearError = useCallback(() => setError(null), []);

  return {
    messages,
    subagentStates,
    liveTraces,
    isConnected,
    isRunning,
    elapsed,
    error,
    planEvent,
    mode,
    setMode,
    sendMessage,
    clearError,
    reviewState,
    approvePlan,
    editPlan,
    sendPlanFeedback,
    approveAssignments,
    editAssignments,
    sendAssignmentsFeedback,
    cancelRun,
  };
}
