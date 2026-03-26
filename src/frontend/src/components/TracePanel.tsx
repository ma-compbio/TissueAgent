import { useState } from "react";
import type { SubagentTranscript, SerializedMessage } from "../types/messages";

interface Props {
  state: SubagentTranscript;
  onClose: () => void;
}

const CODE_PREVIEW_LINES = 12;

/** Render a code block with optional expand for long content. */
function CodeBlock({ code }: { code: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = code.split("\n");
  const isLong = lines.length > CODE_PREVIEW_LINES;
  const displayCode =
    isLong && !expanded
      ? lines.slice(0, CODE_PREVIEW_LINES).join("\n") + "\n..."
      : code;

  return (
    <div className="trace-code-block">
      <pre className="trace-code">{displayCode}</pre>
      {isLong && (
        <button
          className="trace-expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded
            ? "Show less"
            : `Show all (${lines.length} lines)`}
        </button>
      )}
    </div>
  );
}

/** Render a code output block (monospace, no highlighting). */
function OutputBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = text.split("\n");
  const isLong = lines.length > CODE_PREVIEW_LINES;
  const displayText =
    isLong && !expanded
      ? lines.slice(0, CODE_PREVIEW_LINES).join("\n") + "\n..."
      : text;

  return (
    <div className="trace-output-block">
      <span className="trace-step-label">output</span>
      <pre className="trace-output">{displayText}</pre>
      {isLong && (
        <button
          className="trace-expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded
            ? "Show less"
            : `Show all (${lines.length} lines)`}
        </button>
      )}
    </div>
  );
}

/** Check if a HumanMessage is a code execution result (follows an AI with <execute>). */
function isCodeOutput(msg: SerializedMessage, prev: SerializedMessage | null): boolean {
  if (msg.type !== "human") return false;
  if (!prev || prev.type !== "ai") return false;
  return !!(prev.tags && prev.tags["execute"]);
}

/** Render a single step in the trace. */
function TraceStep({
  msg,
  prev,
}: {
  msg: SerializedMessage;
  prev: SerializedMessage | null;
}) {
  const [toolExpanded, setToolExpanded] = useState(false);

  // Code execution output (HumanMessage after an <execute> AI message)
  if (isCodeOutput(msg, prev)) {
    return <OutputBlock text={msg.content || "<no output>"} />;
  }

  // Regular human messages in trace (shouldn't normally appear; skip)
  if (msg.type === "human") {
    return null;
  }

  // AI messages
  if (msg.type === "ai") {
    const tags = msg.tags;
    const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;

    return (
      <div className="trace-ai-step">
        {tags ? (
          Object.entries(tags).map(([tag, content]) => (
            <div key={tag} className="trace-tag-block">
              <span className="trace-step-label">{tag}</span>
              {tag === "execute" ? (
                <CodeBlock code={content} />
              ) : (
                <div className={`trace-tag-content trace-tag-${tag}`}>
                  {content}
                </div>
              )}
            </div>
          ))
        ) : msg.content ? (
          <div className="trace-ai-content">{msg.content}</div>
        ) : null}
        {hasToolCalls && (
          <div className="trace-tool-calls">
            {msg.tool_calls!.map((tc, i) => (
              <span key={i} className="tool-call-pill">
                → {tc.name}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Tool messages
  if (msg.type === "tool") {
    return (
      <div className="trace-tool-step">
        <div
          className="trace-tool-header"
          onClick={() => setToolExpanded(!toolExpanded)}
        >
          <span className="trace-expand-icon">
            {toolExpanded ? "▼" : "▶"}
          </span>
          <span className="trace-step-label">tool: {msg.name || "unknown"}</span>
        </div>
        {toolExpanded && (
          <pre className="trace-tool-content">{msg.content || "<empty>"}</pre>
        )}
      </div>
    );
  }

  return null;
}

export default function TracePanel({ state, onClose }: Props) {
  const transcript = state.transcript || [];

  return (
    <div className="trace-panel">
      <div className="trace-panel-header">
        <div className="trace-panel-title">
          <span className="avatar">{state.avatar}</span>
          <span className="trace-panel-name">{state.agent_name}</span>
        </div>
        <button className="trace-close-btn" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="trace-panel-body">
        {transcript.length === 0 ? (
          <div className="trace-empty">No trace available.</div>
        ) : (
          transcript.map((msg, i) => (
            <TraceStep
              key={i}
              msg={msg}
              prev={i > 0 ? transcript[i - 1] : null}
            />
          ))
        )}
        {state.raw_state && (
          <div className="trace-raw">
            <pre>{state.raw_state}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
