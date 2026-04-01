import { useEffect, useMemo, useRef, useState } from "react";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";
import MessageBubble, { AgentRunCard, type AgentRun } from "./MessageBubble";
import TracePanel from "./TracePanel";

interface Props {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  liveTraces: Record<string, SubagentTranscript>;
  isRunning: boolean;
  elapsed: number | null;
  enableDebug: boolean;
  onSendMessage: (text: string) => void;
}

/**
 * A group is either a standalone message (human, AI without tool_calls)
 * or an AI message bundled with its tool-result messages.
 */
interface MessageGroup {
  ai: SerializedMessage;
  toolResults: SerializedMessage[];
}

type DisplayItem =
  | { kind: "human"; message: SerializedMessage }
  | { kind: "group"; group: MessageGroup }
  | { kind: "agent_run"; run: AgentRun }
  | { kind: "manager_subagent"; message: SerializedMessage };

const MAIN_AGENT_NAMES = new Set([
  "planner_agent",
  "recruiter_agent",
  "manager_agent",
  "evaluator_agent",
  "reporter_agent",
]);

/** Group AI messages with their tool result messages matched by ID. */
function buildDisplayItems(messages: SerializedMessage[]): DisplayItem[] {
  // Index tool messages by tool_call_id for ID-based matching
  const toolMsgByCallId = new Map<string, SerializedMessage>();
  for (const msg of messages) {
    if (msg.type === "tool" && msg.tool_call_id) {
      toolMsgByCallId.set(msg.tool_call_id, msg);
    }
  }

  const consumed = new Set<string>();
  const items: DisplayItem[] = [];

  for (const msg of messages) {
    if (msg.type === "human") {
      items.push({ kind: "human", message: msg });
      continue;
    }

    if (msg.type === "ai") {
      const toolResults: SerializedMessage[] = [];
      if (msg.tool_calls?.length) {
        for (const tc of msg.tool_calls) {
          if (tc.id && toolMsgByCallId.has(tc.id)) {
            toolResults.push(toolMsgByCallId.get(tc.id)!);
            consumed.add(tc.id);
          }
        }
      }
      items.push({ kind: "group", group: { ai: msg, toolResults } });
      continue;
    }

    if (msg.type === "tool") {
      // Skip if already matched to its parent AI message
      if (msg.tool_call_id && consumed.has(msg.tool_call_id)) continue;
      // Orphan tool message — render standalone
      items.push({ kind: "group", group: { ai: msg, toolResults: [] } });
      continue;
    }
  }

  return items;
}

/**
 * Collapse consecutive groups from the same main agent into AgentRun items.
 * Subagent tool results (transfer tools with SubagentTranscripts) inside
 * manager groups are extracted as separate `manager_subagent` items, which
 * splits the manager run into multiple blocks.
 */
function collapseAgentRuns(
  items: DisplayItem[],
  subagentStates: Record<string, SubagentTranscript>,
): DisplayItem[] {
  const result: DisplayItem[] = [];
  let runCounter = 0;

  const isSubagentTool = (msg: SerializedMessage): boolean =>
    msg.type === "tool" && !!msg.id && !!subagentStates[msg.id];

  const flushRun = (groups: MessageGroup[], agentName: string, firstAi: SerializedMessage) => {
    if (groups.length === 0) return;
    const allMessages: SerializedMessage[] = [];
    for (const g of groups) {
      allMessages.push(g.ai);
      allMessages.push(...g.toolResults);
    }
    result.push({
      kind: "agent_run",
      run: {
        agentName,
        avatar: firstAi.avatar,
        label: firstAi.label ?? agentName,
        messages: allMessages,
        syntheticId: `run-${agentName}-${runCounter++}`,
      },
    });
  };

  let i = 0;
  while (i < items.length) {
    const item = items[i];

    if (item.kind === "group" && item.group.ai.name && MAIN_AGENT_NAMES.has(item.group.ai.name)) {
      const agentName = item.group.ai.name;
      const pendingGroups: MessageGroup[] = [];
      let firstAi: SerializedMessage | null = null;

      // Process consecutive groups from the same agent
      while (i < items.length) {
        const current = items[i];
        if (current.kind !== "group" || current.group.ai.name !== agentName) break;

        if (!firstAi) firstAi = current.group.ai;
        const { ai, toolResults } = current.group;

        // Split tool results: subagent transfer tools vs. agent's own tools
        const subagentTools = toolResults.filter(isSubagentTool);
        const normalTools = toolResults.filter((tr) => !isSubagentTool(tr));

        if (subagentTools.length > 0) {
          // Add AI + normal tools to pending run, then flush
          pendingGroups.push({ ai, toolResults: normalTools });
          flushRun(pendingGroups, agentName, firstAi);
          pendingGroups.length = 0;

          // Emit each subagent tool result as a separate card
          for (const st of subagentTools) {
            result.push({ kind: "manager_subagent", message: st });
          }
          // Reset firstAi so next run segment picks it up fresh
          firstAi = null;
        } else {
          pendingGroups.push(current.group);
        }

        i++;
      }

      // Flush remaining groups
      if (pendingGroups.length > 0 && firstAi) {
        flushRun(pendingGroups, agentName, firstAi);
      }
      continue;
    }

    result.push(item);
    i++;
  }

  return result;
}

/** Build synthetic SubagentTranscripts from AgentRun items. */
function buildSyntheticTraces(
  items: DisplayItem[]
): Record<string, SubagentTranscript> {
  const traces: Record<string, SubagentTranscript> = {};
  for (const item of items) {
    if (item.kind !== "agent_run") continue;
    const { run } = item;
    traces[run.syntheticId] = {
      tool_id: run.syntheticId,
      agent_name: run.label,
      avatar: run.avatar,
      transcript: run.messages,
      raw_state: null,
    };
  }
  return traces;
}

export default function ChatView({
  messages,
  subagentStates,
  liveTraces,
  isRunning,
  elapsed,
  enableDebug,
  onSendMessage,
}: Props) {
  const [input, setInput] = useState("");
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
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

  const getSubagentState = (msg: SerializedMessage): SubagentTranscript | undefined => {
    if (msg.type !== "tool" || !msg.id) return undefined;
    return subagentStates[msg.id];
  };

  const handleSelectTrace = (toolId: string) => {
    setSelectedTrace(selectedTrace === toolId ? null : toolId);
  };

  const rawItems = buildDisplayItems(messages);
  const displayItems = collapseAgentRuns(rawItems, subagentStates);
  const syntheticTraces = useMemo(() => buildSyntheticTraces(displayItems), [displayItems]);

  const activeTrace = selectedTrace
    ? (liveTraces[selectedTrace] ?? syntheticTraces[selectedTrace] ?? subagentStates[selectedTrace] ?? null)
    : null;

  return (
    <div className={activeTrace ? "chat-two-column" : "chat-layout"}>
      <div className={activeTrace ? "chat-column-left" : "chat-column-full"}>
        <div className="chat-view">
          <div className="chat-messages" ref={containerRef}>
            {displayItems.map((item, i) => {
              if (item.kind === "human") {
                return (
                  <MessageBubble
                    key={`human-${item.message.id ?? i}`}
                    message={item.message}
                    enableDebug={enableDebug}
                    onSelectTrace={handleSelectTrace}
                    selectedTraceId={selectedTrace}
                  />
                );
              }

              if (item.kind === "agent_run") {
                return (
                  <AgentRunCard
                    key={item.run.syntheticId}
                    run={item.run}
                    onSelectTrace={handleSelectTrace}
                    isSelected={selectedTrace === item.run.syntheticId}
                  />
                );
              }

              if (item.kind === "manager_subagent") {
                const state = getSubagentState(item.message);
                if (!state || !item.message.id) return null;
                return (
                  <div key={`msa-${item.message.id}`} className="manager-subagent-wrapper">
                    <MessageBubble
                      message={item.message}
                      subagentState={state}
                      enableDebug={enableDebug}
                      onSelectTrace={handleSelectTrace}
                      selectedTraceId={selectedTrace}
                    />
                  </div>
                );
              }

              const { ai, toolResults } = item.group;
              // Check if any tool result is a subagent
              const subagentResults = toolResults.filter(
                (tr) => getSubagentState(tr) !== undefined
              );
              const nonSubagentResults = toolResults.filter(
                (tr) => getSubagentState(tr) === undefined
              );

              return (
                <div key={`group-${ai.id ?? i}`} className="message-group">
                  <MessageBubble
                    message={ai}
                    subagentState={ai.type === "tool" ? getSubagentState(ai) : undefined}
                    enableDebug={enableDebug}
                    onSelectTrace={handleSelectTrace}
                    selectedTraceId={selectedTrace}
                  />
                  {/* Subagent cards — always visible */}
                  {subagentResults.map((tr) => (
                    <MessageBubble
                      key={`sa-${tr.id}`}
                      message={tr}
                      subagentState={getSubagentState(tr)}
                      enableDebug={enableDebug}
                      onSelectTrace={handleSelectTrace}
                      selectedTraceId={selectedTrace}
                    />
                  ))}
                  {/* Non-subagent tool results (debug only) */}
                  {enableDebug &&
                    nonSubagentResults.map((tr, j) => (
                      <MessageBubble
                        key={`tool-${tr.id ?? j}`}
                        message={tr}
                        enableDebug={enableDebug}
                        onSelectTrace={handleSelectTrace}
                        selectedTraceId={selectedTrace}
                      />
                    ))}
                </div>
              );
            })}

            {/* Live sub-agent cards (currently running) */}
            {Object.entries(liveTraces).map(([invId, trace]) => (
              <div key={`live-${invId}`} className="manager-subagent-wrapper">
                <div
                  className={`subagent-card subagent-card-live ${selectedTrace === invId ? "subagent-card-selected" : ""}`}
                  onClick={() => handleSelectTrace(invId)}
                >
                  <div className="subagent-card-header">
                    <span className="avatar">{trace.avatar}</span>
                    <span className="subagent-card-name">{trace.agent_name}</span>
                    <span className="subagent-card-action">
                      <span className="live-dot" />
                      {selectedTrace === invId ? "Viewing live trace" : "View live trace"}
                    </span>
                  </div>
                  {trace.transcript && trace.transcript.length > 0 && (
                    <div className="subagent-card-output">
                      Step {trace.transcript.filter((m) => m.type === "ai").length} in progress...
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isRunning && Object.keys(liveTraces).length === 0 && (
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
      </div>

      {activeTrace && (
        <div className="chat-column-right">
          <TracePanel
            state={activeTrace}
            onClose={() => setSelectedTrace(null)}
          />
        </div>
      )}
    </div>
  );
}
