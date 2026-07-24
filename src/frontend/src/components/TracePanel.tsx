import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { SubagentTranscript, SerializedMessage, ToolCall } from "../types/messages";
import AgentAvatar from "./AgentAvatar";
import TraceSkills from "./TraceSkills";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

const CODE_TOOLS: Record<string, string> = {
  python: "python",
  r: "r",
};

interface Props {
  state: SubagentTranscript;
  /** Active project id — required to resolve project-scoped image URLs. */
  projectId: string;
  onClose: () => void;
}

const CODE_PREVIEW_LINES = 12;

/** Render coding-agent plot images from their project-relative paths. */
function TraceImages({
  paths,
  projectId,
}: {
  paths: string[];
  projectId: string;
}) {
  if (!paths.length) return null;
  return (
    <div className="trace-images">
      {paths.map((p, i) => {
        const url = `${API}/api/files/download/${p}?scope=project&project_id=${encodeURIComponent(
          projectId,
        )}&inline=1`;
        return (
          <img
            key={i}
            src={url}
            alt="plot output"
            className="trace-image"
            loading="lazy"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        );
      })}
    </div>
  );
}

function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
  );
}

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

/** Collapsible dropdown at the top of the trace exposing the exact system
 *  prompt the sub-agent ran with, plus the skills that were loaded. Collapsed
 *  by default so it doesn't push the transcript down. */
function TraceContext({
  systemPrompt,
  skills,
}: {
  systemPrompt?: string | null;
  skills?: string[];
}) {
  const [open, setOpen] = useState(false);
  const hasPrompt = !!systemPrompt;
  const hasSkills = !!skills && skills.length > 0;
  if (!hasPrompt && !hasSkills) return null;

  return (
    <div className="trace-context">
      <button
        className="trace-context-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="trace-expand-icon">{open ? "▼" : "▶"}</span>
        <span className="trace-step-label">System prompt &amp; skills</span>
      </button>
      {open && (
        <div className="trace-context-body">
          {hasPrompt && (
            <div className="trace-system-prompt">
              <span className="trace-step-label">system prompt</span>
              <pre className="trace-system-prompt-content">{systemPrompt}</pre>
            </div>
          )}
          {hasSkills && <TraceSkills skills={skills!} />}
        </div>
      )}
    </div>
  );
}

/** Render a single step in the trace. */
function TraceStep({
  msg,
  prev,
  toolCallMap,
  projectId,
}: {
  msg: SerializedMessage;
  prev: SerializedMessage | null;
  toolCallMap: Map<string, ToolCall>;
  projectId: string;
}) {
  const [toolExpanded, setToolExpanded] = useState(false);
  const images = msg.image_paths ?? [];

  // Code execution output (HumanMessage after an <execute> AI message)
  if (isCodeOutput(msg, prev)) {
    return (
      <>
        <OutputBlock text={msg.content || "<no output>"} />
        <TraceImages paths={images} projectId={projectId} />
      </>
    );
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
                  <Markdown>{content}</Markdown>
                </div>
              )}
            </div>
          ))
        ) : msg.content ? (
          <div className="trace-ai-content"><Markdown>{msg.content}</Markdown></div>
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
    const matchedCall = msg.tool_call_id ? toolCallMap.get(msg.tool_call_id) : null;
    const toolName = msg.name || "unknown";
    const codeLang = matchedCall ? CODE_TOOLS[matchedCall.name] : undefined;

    const renderInputs = () => {
      if (!matchedCall) return null;
      if (codeLang && typeof matchedCall.args.code === "string") {
        return (
          <SyntaxHighlighter
            language={codeLang}
            style={oneLight}
            customStyle={{ fontSize: "0.8rem", borderRadius: "0.4rem", margin: 0 }}
          >
            {matchedCall.args.code}
          </SyntaxHighlighter>
        );
      }
      return (
        <pre className="trace-tool-content">
          {JSON.stringify(matchedCall.args, null, 2)}
        </pre>
      );
    };

    return (
      <div className="trace-tool-step">
        <div
          className="trace-tool-header"
          onClick={() => setToolExpanded(!toolExpanded)}
        >
          <span className="trace-expand-icon">
            {toolExpanded ? "▼" : "▶"}
          </span>
          <span className="trace-step-label">tool: {toolName}</span>
        </div>
        {toolExpanded && (
          <div className="trace-tool-body">
            {matchedCall && (
              <div className="trace-tool-inputs">
                <span className="trace-step-label">inputs</span>
                {renderInputs()}
              </div>
            )}
            <div className="trace-tool-output">
              <span className="trace-step-label">output</span>
              <pre className="trace-tool-content">{msg.content || "<empty>"}</pre>
              <TraceImages paths={images} projectId={projectId} />
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}

export default function TracePanel({ state, projectId, onClose }: Props) {
  const transcript = state.transcript || [];

  // Build a map from tool_call_id -> ToolCall for quick lookup when rendering tool messages
  const toolCallMap = new Map<string, ToolCall>();
  for (const msg of transcript) {
    if (msg.type === "ai" && msg.tool_calls) {
      for (const tc of msg.tool_calls) {
        if (tc.id) toolCallMap.set(tc.id, tc);
      }
    }
  }

  return (
    <div className="trace-panel">
      <div className="trace-panel-header">
        <div className="trace-panel-title">
          <AgentAvatar
            name={state.agent_name}
            fallback={state.avatar}
            size={22}
          />
          <span className="trace-panel-name">{state.agent_name}</span>
        </div>
        <button className="trace-close-btn" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="trace-panel-body">
        <TraceContext
          systemPrompt={state.system_prompt}
          skills={state.skills}
        />
        {transcript.length === 0 ? (
          <div className="trace-empty">No trace available.</div>
        ) : (
          transcript.map((msg, i) => (
            <TraceStep
              key={i}
              msg={msg}
              prev={i > 0 ? transcript[i - 1] : null}
              toolCallMap={toolCallMap}
              projectId={projectId}
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
