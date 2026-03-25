import { useCallback, useEffect, useRef, useState } from "react";
import type {
  HistoryData,
  SendMessageEvent,
  SerializedMessage,
  ServerEvent,
  SubagentTranscript,
} from "../types/messages";

interface UseWebSocketReturn {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  isConnected: boolean;
  isRunning: boolean;
  elapsed: number | null;
  error: string | null;
  sendMessage: (text: string, imageIds?: string[], pdfIds?: string[]) => void;
  clearError: () => void;
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
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        case "subagent_state": {
          const state = data.data as SubagentTranscript;
          if (state.tool_id !== "pending") {
            setSubagentStates((prev) => ({
              ...prev,
              [state.tool_id]: state,
            }));
          }
          break;
        }
        case "run_complete":
          setIsRunning(false);
          setElapsed(data.elapsed_seconds);
          break;
        case "run_error":
          setIsRunning(false);
          setError(`${data.error_type}: ${data.detail}`);
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

  const sendMessage = useCallback(
    (text: string, imageIds: string[] = [], pdfIds: string[] = []) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError("Not connected to server");
        return;
      }
      const event: SendMessageEvent = {
        type: "send_message",
        text,
        image_ids: imageIds,
        pdf_ids: pdfIds,
      };
      wsRef.current.send(JSON.stringify(event));
    },
    []
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    messages,
    subagentStates,
    isConnected,
    isRunning,
    elapsed,
    error,
    sendMessage,
    clearError,
  };
}
