import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";

export interface AgentRun {
  agentName: string;
  avatar: string;
  label: string;
  messages: SerializedMessage[];
  syntheticId: string;
}

interface Props {
  message: SerializedMessage;
  subagentState?: SubagentTranscript;
  enableDebug: boolean;
  onSelectTrace: (toolId: string) => void;
  selectedTraceId: string | null;
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

/** Extract the final output from a subagent transcript. */
function extractFinalOutput(state: SubagentTranscript): string | null {
  if (!state.transcript) return null;
  // Walk backwards to find the last AI message with a <response> tag or content
  for (let i = state.transcript.length - 1; i >= 0; i--) {
    const msg = state.transcript[i];
    if (msg.type !== "ai") continue;
    if (msg.tags?.response) return msg.tags.response;
    if (msg.content) return msg.content;
  }
  return null;
}

/** Compact subagent card shown in the left conversation column. */
function SubagentCard({
  toolId,
  state,
  onSelectTrace,
  isSelected,
}: {
  toolId: string;
  state: SubagentTranscript;
  onSelectTrace: (toolId: string) => void;
  isSelected: boolean;
}) {
  const finalOutput = extractFinalOutput(state);

  return (
    <div
      className={`subagent-card ${isSelected ? "subagent-card-selected" : ""}`}
      onClick={() => onSelectTrace(toolId)}
    >
      <div className="subagent-card-header">
        <span className="avatar">{state.avatar}</span>
        <span className="subagent-card-name">{state.agent_name}</span>
        <span className="subagent-card-action">
          {isSelected ? "▼ Hide trace" : "▶ View trace"}
        </span>
      </div>
      {finalOutput && (
        <div className="subagent-card-output">
          {finalOutput.length > 300
            ? finalOutput.slice(0, 300) + "..."
            : finalOutput}
        </div>
      )}
    </div>
  );
}

/** Clickable card for a main pipeline agent run (Planner, Manager, etc.). */
export function AgentRunCard({
  run,
  onSelectTrace,
  isSelected,
}: {
  run: AgentRun;
  onSelectTrace: (id: string) => void;
  isSelected: boolean;
}) {
  // Summarize: find the last high-level tag content, or list tool call names
  let summary: string | null = null;
  for (let i = run.messages.length - 1; i >= 0; i--) {
    const msg = run.messages[i];
    if (msg.type !== "ai") continue;
    if (msg.tags?.response) { summary = msg.tags.response; break; }
    if (msg.tags?.plan) { summary = msg.tags.plan; break; }
    if (msg.body?.trim()) { summary = msg.body; break; }
    if (msg.content?.trim()) { summary = msg.content; break; }
  }

  return (
    <div
      className={`subagent-card ${isSelected ? "subagent-card-selected" : ""}`}
      onClick={() => onSelectTrace(run.syntheticId)}
    >
      <div className="subagent-card-header">
        <span className="avatar">{run.avatar}</span>
        <span className="subagent-card-name">{run.label}</span>
        <span className="subagent-card-action">
          {isSelected ? "▼ Hide trace" : "▶ View trace"}
        </span>
      </div>
      {summary && (
        <div className="subagent-card-output">
          {summary.length > 300 ? summary.slice(0, 300) + "..." : summary}
        </div>
      )}
    </div>
  );
}

/** Render a tool call with collapsible input/output (debug mode, no subagent). */
function ToolCallMessage({
  message,
}: {
  message: SerializedMessage;
}) {
  return (
    <div className="message-bubble tool-message">
      <div className="tool-header">
        <span className="tool-icon">🔧</span>
        <span className="tool-name">{message.name || "Tool"}</span>
      </div>
    </div>
  );
}

export default function MessageBubble({
  message,
  subagentState,
  enableDebug,
  onSelectTrace,
  selectedTraceId,
}: Props) {
  // Tool messages
  if (message.type === "tool") {
    // If this tool message has a subagent state, show a compact card
    if (subagentState && message.id) {
      return (
        <SubagentCard
          toolId={message.id}
          state={subagentState}
          onSelectTrace={onSelectTrace}
          isSelected={selectedTraceId === message.id}
        />
      );
    }
    // Otherwise show as debug tool message
    if (!enableDebug) return null;
    return <ToolCallMessage message={message} />;
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
    const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;

    // Determine what to display in the high-level left panel.
    // Only response and plan tags are high-level; execute/scratchpad are intermediate.
    let displayContent: React.ReactNode = null;

    if (tags) {
      const highLevelEntries = Object.entries(tags).filter(
        ([tag]) => tag === "response" || tag === "plan"
      );

      if (highLevelEntries.length > 0) {
        displayContent = (
          <>
            {highLevelEntries.map(([tag, content]) => (
              <TagBlock key={tag} tag={tag} content={content} />
            ))}
          </>
        );
      } else if (enableDebug) {
        // Debug mode: show all tags
        displayContent = (
          <>
            {Object.entries(tags).map(([tag, content]) => (
              <TagBlock key={tag} tag={tag} content={content} />
            ))}
          </>
        );
      } else {
        // Only intermediate tags — hide this message
        return null;
      }
    } else if (body?.trim()) {
      displayContent = <FormattedContent text={body} />;
    } else if (hasToolCalls && !enableDebug) {
      // Empty body with only tool calls — hide unless debug
      return null;
    }

    if (!displayContent && !enableDebug) return null;

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
          {displayContent}
          {enableDebug && hasToolCalls && (
            <div className="tool-calls-summary">
              {message.tool_calls!.map((tc, i) => (
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
