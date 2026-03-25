import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { SubagentTranscript, SerializedMessage } from "../types/messages";

interface Props {
  state: SubagentTranscript;
}

function SubMessage({ msg }: { msg: SerializedMessage }) {
  const [expanded, setExpanded] = useState(false);

  if (msg.type === "tool") {
    return (
      <div className="sub-tool-message">
        <div
          className="sub-tool-header"
          onClick={() => setExpanded(!expanded)}
          style={{ cursor: "pointer" }}
        >
          <span>{expanded ? "▼" : "▶"}</span>
          <span className="sub-tool-name">{msg.name || "Tool"}</span>
        </div>
        {expanded && (
          <div className="sub-tool-content">
            <SyntaxHighlighter
              language="json"
              style={oneLight}
              customStyle={{ fontSize: "0.8rem" }}
            >
              {msg.content || "<empty>"}
            </SyntaxHighlighter>
          </div>
        )}
      </div>
    );
  }

  if (msg.type === "ai") {
    const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;
    return (
      <div className="sub-ai-message">
        <span className="sub-agent-label">[{msg.name || "Agent"}]</span>
        {hasToolCalls ? (
          <span className="sub-tool-calls">
            → {msg.tool_calls!.map((tc) => tc.name).join(", ")}
          </span>
        ) : msg.content ? (
          <div className="sub-ai-content">{msg.content}</div>
        ) : null}
      </div>
    );
  }

  return null;
}

export default function SubagentTrace({ state }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="subagent-trace">
      <div
        className="subagent-header"
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: "pointer" }}
      >
        <span className="avatar">{state.avatar}</span>
        <span className="subagent-name">{state.agent_name}</span>
        <span className="expand-icon">{expanded ? "▼" : "▶"}</span>
      </div>
      {expanded && (
        <div className="subagent-body">
          {state.transcript ? (
            state.transcript.map((msg, i) => (
              <SubMessage key={i} msg={msg} />
            ))
          ) : state.raw_state ? (
            <div className="subagent-raw">{state.raw_state}</div>
          ) : (
            <div className="subagent-empty">No transcript available.</div>
          )}
        </div>
      )}
    </div>
  );
}
