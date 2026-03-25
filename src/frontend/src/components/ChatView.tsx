import { useEffect, useRef, useState } from "react";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";
import MessageBubble from "./MessageBubble";

interface Props {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  isRunning: boolean;
  elapsed: number | null;
  enableDebug: boolean;
  onSendMessage: (text: string) => void;
}

export default function ChatView({
  messages,
  subagentStates,
  isRunning,
  elapsed,
  enableDebug,
  onSendMessage,
}: Props) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isRunning) return;
    onSendMessage(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  /** Find matching subagent state for a tool message. */
  const getSubagentState = (msg: SerializedMessage): SubagentTranscript | undefined => {
    if (msg.type !== "tool" || !msg.id) return undefined;
    return subagentStates[msg.id];
  };

  return (
    <div className="chat-view">
      <div className="chat-messages" ref={containerRef}>
        {messages.map((msg, i) => (
          <MessageBubble
            key={`${msg.id ?? i}-${i}`}
            message={msg}
            subagentState={getSubagentState(msg)}
            enableDebug={enableDebug}
          />
        ))}

        {isRunning && (
          <div className="thinking-indicator">
            <div className="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <span>TissueAgent is thinking...</span>
          </div>
        )}

        {elapsed !== null && !isRunning && (
          <div className="elapsed-time">
            Completed in {elapsed.toFixed(1)}s
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isRunning ? "Agent is running..." : "Ask the agent..."}
          disabled={isRunning}
          rows={1}
        />
        <button
          type="submit"
          className="send-button"
          disabled={isRunning || !input.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
