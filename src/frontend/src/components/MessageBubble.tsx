import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";
import AgentAvatar from "./AgentAvatar";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

/** Resolve a markdown image src into a loadable URL.
 *
 * The reporter embeds figures as project-relative paths (e.g.
 * `outputs/figures/umap.png`). Rewrite those to the file-download endpoint;
 * pass through absolute/http/data URLs untouched. Returns null when the src
 * can't be resolved to a project-relative path (renders nothing).
 */
function resolveFigureSrc(
  src: string | undefined,
  projectId: string,
): string | null {
  if (!src) return null;
  if (/^(https?:|data:)/i.test(src)) return src;
  // Normalize: strip leading slashes and a stray "project/" prefix.
  let rel = src.replace(/^\/+/, "").replace(/^project\//, "");
  if (!rel.startsWith("outputs/")) return null;
  if (!projectId) return null;
  return `${API}/api/files/download/${rel}?scope=project&project_id=${encodeURIComponent(
    projectId,
  )}&inline=1`;
}

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

// Prism turns each code block into a large tree of <span> nodes. Over a long
// session, big blocks (compiler command lines, install logs, tool dumps)
// accumulate in the DOM and balloon the renderer's memory until Chromium
// traps with SIGTRAP. Above this size we skip highlighting and render plain
// preformatted text (a single cheap text node) instead.
const MAX_HIGHLIGHT_CHARS = 8000;
// Above this size, keep the block collapsed by default so a single huge dump
// doesn't sit in the DOM (even off-screen) as a giant node.
const MAX_INLINE_CHARS = 20000;

/** A code block that degrades gracefully as content grows. */
function CodeBlock({ code, language }: { code: string; language: string }) {
  const [expanded, setExpanded] = useState(false);

  // Small enough to highlight safely.
  if (code.length <= MAX_HIGHLIGHT_CHARS) {
    return (
      <SyntaxHighlighter
        language={language}
        style={oneLight}
        customStyle={{ fontSize: "0.85rem", borderRadius: "0.4rem" }}
      >
        {code}
      </SyntaxHighlighter>
    );
  }

  const collapsed = code.length > MAX_INLINE_CHARS && !expanded;
  const shown = collapsed ? code.slice(0, MAX_INLINE_CHARS) : code;

  return (
    <div style={{ marginTop: "0.25rem" }}>
      <pre
        className="plain-code-block"
        style={{
          fontSize: "0.85rem",
          background: "#f8f9fa",
          borderRadius: "0.4rem",
          padding: "0.6rem 0.75rem",
          margin: 0,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          overflowX: "auto",
          maxHeight: expanded ? "none" : "24rem",
        }}
      >
        {shown}
        {collapsed ? "\n…" : ""}
      </pre>
      {code.length > MAX_INLINE_CHARS && (
        <button
          type="button"
          className="code-toggle"
          onClick={() => setExpanded((v) => !v)}
          style={{
            marginTop: "0.35rem",
            fontSize: "0.75rem",
            cursor: "pointer",
            background: "none",
            border: "none",
            padding: 0,
            color: "#3b82f6",
          }}
        >
          {expanded
            ? "Show less"
            : `Show more (${code.length.toLocaleString()} chars)`}
        </button>
      )}
    </div>
  );
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
        <CodeBlock language="python" code={content} />
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
          return <CodeBlock key={i} language={lang} code={code} />;
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
        <AgentAvatar name={state.agent_name} fallback={state.avatar} size={22} />
        <span className="subagent-card-name">{state.agent_name}</span>
        <span className="subagent-card-action">
          {isSelected ? "▼ Hide trace" : "▶ View trace"}
        </span>
      </div>
      {finalOutput && (
        <div className="subagent-card-output">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {finalOutput}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

/** Routes on which the planner answers the user itself and the graph goes
 *  straight to END — no recruiter, manager, or reporter ever runs. On these the
 *  planner's own message body IS the final answer, so it must be surfaced the
 *  same way the reporter's is. See `planner_router` in graph/graph.py. */
const TERMINAL_PLANNER_ROUTES = new Set(["DIRECT", "CLARIFY"]);

/** Return the planner's answer text when a run terminated on DIRECT/CLARIFY.
 *
 *  Returns null for any other run — including a ROUTE: PLAN planner run, whose
 *  body is the raw JSON plan and must stay folded inside the trace. Only the
 *  last AI message is considered, since that is the one the router acted on;
 *  earlier turns in the same run may be retries or tool-calling rounds. */
export function extractTerminalPlannerAnswer(
  run: AgentRun,
): string | null {
  if (run.agentName !== "planner_agent") return null;
  for (let i = run.messages.length - 1; i >= 0; i--) {
    const msg = run.messages[i];
    if (msg.type !== "ai") continue;
    // Mid-run tool-calling turns carry no route header; keep looking back.
    if (msg.tool_calls && msg.tool_calls.length > 0) continue;
    if (!msg.route || !TERMINAL_PLANNER_ROUTES.has(msg.route.toUpperCase())) {
      return null;
    }
    const text = msg.body?.trim() || msg.content?.trim() || "";
    return text || null;
  }
  return null;
}

/** Extract the final response text from an agent run's messages. */
export function extractFinalResponse(messages: SerializedMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.type !== "ai") continue;
    if (msg.tags?.response) return msg.tags.response;
    if (msg.tags?.plan) return msg.tags.plan;
    if (msg.body?.trim()) return msg.body;
    if (msg.content?.trim()) return msg.content;
  }
  return null;
}

/** Full-width box showing the reporter's final answer, rendered in markdown. */
export function FinalAnswerBox({
  content,
  projectId = "",
}: {
  content: string;
  projectId?: string;
}) {
  return (
    <div className="final-answer-box">
      <div className="final-answer-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt }) => {
              const url = resolveFigureSrc(src as string | undefined, projectId);
              if (!url) return null;
              return (
                <img
                  src={url}
                  alt={alt ?? "figure"}
                  className="final-figure"
                  loading="lazy"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
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
  // Planner and recruiter output raw JSON that isn't useful as a preview —
  // hide the summary for them and let the user open the trace to see it.
  // Exception: a planner run that ended on DIRECT/CLARIFY answered the user in
  // prose instead of emitting a plan, and that answer is rendered below the
  // card as a FinalAnswerBox — so suppress the summary there too, rather than
  // showing the same text twice.
  const suppressSummary =
    run.agentName === "planner_agent" || run.agentName === "recruiter_agent";

  // Summarize: find the last high-level tag content, or list tool call names
  let summary: string | null = null;
  if (!suppressSummary) {
    for (let i = run.messages.length - 1; i >= 0; i--) {
      const msg = run.messages[i];
      if (msg.type !== "ai") continue;
      if (msg.tags?.response) { summary = msg.tags.response; break; }
      if (msg.tags?.plan) { summary = msg.tags.plan; break; }
      if (msg.body?.trim()) { summary = msg.body; break; }
      if (msg.content?.trim()) { summary = msg.content; break; }
    }
  }

  return (
    <div
      className={`subagent-card ${isSelected ? "subagent-card-selected" : ""}`}
      onClick={() => onSelectTrace(run.syntheticId)}
    >
      <div className="subagent-card-header">
        <AgentAvatar name={run.agentName} fallback={run.avatar} size={22} />
        <span className="subagent-card-name">{run.label}</span>
        <span className="subagent-card-action">
          {isSelected ? "▼ Hide trace" : "▶ View trace"}
        </span>
      </div>
      {summary && (
        <div className="subagent-card-output">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {summary}
          </ReactMarkdown>
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
          <AgentAvatar name={message.name} fallback={message.avatar} size={20} />
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
          <AgentAvatar name={message.name} fallback={message.avatar} size={20} />
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
