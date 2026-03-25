import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";
import SubagentTrace from "./SubagentTrace";

interface Props {
  message: SerializedMessage;
  subagentState?: SubagentTranscript;
  enableDebug: boolean;
}

/** Render a tagged content block (<execute>, <scratchpad>, etc.) */
function TagBlock({ tag, content }: { tag: string; content: string }) {
  const styles: Record<string, React.CSSProperties> = {
    execute: { background: "#f8f9fa", borderLeft: "3px solid #6c757d" },
    response: { background: "#f0fdf4", borderLeft: "3px solid #22c55e" },
    scratchpad: { background: "#fefce8", borderLeft: "3px solid #eab308" },
    plan: { background: "#eff6ff", borderLeft: "3px solid #3b82f6" },
  };

  const isCode = tag === "execute";

  return (
    <div style={{ marginTop: "0.5rem" }}>
      <span className="tag-label">{tag}</span>
      {isCode ? (
        <SyntaxHighlighter
          language="python"
          style={oneLight}
          customStyle={{ fontSize: "0.85rem", borderRadius: "0.4rem" }}
        >
          {content}
        </SyntaxHighlighter>
      ) : (
        <div className="tag-block" style={styles[tag] || {}}>
          {content}
        </div>
      )}
    </div>
  );
}

/** Render markdown-like content with code fences. */
function FormattedContent({ text }: { text: string }) {
  const parts = text.split(/(```[\s\S]*?```)/g);

  return (
    <>
      {parts.map((part, i) => {
        const fenceMatch = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
        if (fenceMatch) {
          const lang = fenceMatch[1] || "text";
          const code = fenceMatch[2].trim();
          return (
            <SyntaxHighlighter
              key={i}
              language={lang}
              style={oneLight}
              customStyle={{ fontSize: "0.85rem", borderRadius: "0.4rem" }}
            >
              {code}
            </SyntaxHighlighter>
          );
        }
        if (part.trim()) {
          return (
            <div key={i} style={{ whiteSpace: "pre-wrap" }}>
              {part}
            </div>
          );
        }
        return null;
      })}
    </>
  );
}

/** Render a tool call with collapsible input/output. */
function ToolCallMessage({
  message,
  subagentState,
}: {
  message: SerializedMessage;
  subagentState?: SubagentTranscript;
}) {
  const [expanded, setExpanded] = useState(false);

  if (subagentState) {
    return <SubagentTrace state={subagentState} />;
  }

  return (
    <div className="message-bubble tool-message">
      <div
        className="tool-header"
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: "pointer" }}
      >
        <span className="tool-icon">🔧</span>
        <span className="tool-name">{message.name || "Tool"}</span>
        <span className="expand-icon">{expanded ? "▼" : "▶"}</span>
      </div>
      {expanded && (
        <div className="tool-output">
          <FormattedContent text={message.content || "<empty>"} />
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({
  message,
  subagentState,
  enableDebug,
}: Props) {
  // Tool messages
  if (message.type === "tool") {
    if (!enableDebug) return null;
    return (
      <ToolCallMessage message={message} subagentState={subagentState} />
    );
  }

  // Human messages
  if (message.type === "human") {
    return (
      <div className="message-bubble user-message">
        <div className="message-header">
          <span className="avatar">{message.avatar}</span>
          <span className="label">You</span>
        </div>
        <div className="message-body">
          <FormattedContent text={message.content} />
        </div>
      </div>
    );
  }

  // AI messages
  if (message.type === "ai") {
    if (!message.content && !message.tool_calls?.length) return null;

    const body = message.body ?? message.content;
    const tags = message.tags;

    return (
      <div className="message-bubble ai-message">
        <div className="message-header">
          <span className="avatar">{message.avatar}</span>
          <span className="label">{message.label}</span>
          {message.route && (
            <span className="route-pill">{message.route}</span>
          )}
        </div>
        <div className="message-body">
          {tags ? (
            Object.entries(tags).map(([tag, content]) => (
              <TagBlock key={tag} tag={tag} content={content} />
            ))
          ) : (
            <FormattedContent text={body} />
          )}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="tool-calls-summary">
              {message.tool_calls.map((tc, i) => (
                <span key={i} className="tool-call-pill">
                  → {tc.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}
