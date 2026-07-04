import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { SerializedMessage, SubagentTranscript } from "../types/messages";
import AgentAvatar from "./AgentAvatar";
import MessageBubble, { AgentRunCard, FinalAnswerBox, extractFinalResponse, type AgentRun } from "./MessageBubble";
import ResizeDivider from "./ResizeDivider";
import TracePanel from "./TracePanel";

// The chat input no longer has a fixed height — it auto-grows with its
// content up to this cap (≈ 12 lines), then scrolls inside the bubble.
// Picked so a long paste doesn't push the chat messages off-screen.
const CHAT_INPUT_MAX_PX = 240;

interface Props {
  messages: SerializedMessage[];
  subagentStates: Record<string, SubagentTranscript>;
  liveTraces: Record<string, SubagentTranscript>;
  isRunning: boolean;
  elapsed: number | null;
  enableDebug: boolean;
  onSendMessage: (text: string) => void;
  /** Called when the user picks files via the chat-input "+" button.
   *  The handler routes to the active project's ``uploads/`` directory
   *  (minting the project if none is active). */
  onUploadFiles: (files: FileList) => Promise<void> | void;
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

/**
 * Find the name of the tool call currently in progress for a live trace.
 * Walks the transcript backwards to the most recent AI message with
 * ``tool_calls``, and returns the last one — which is the call the agent
 * has just issued and is waiting on. Returns null if no tool call has
 * been made yet in this step.
 */
function extractCurrentToolCall(trace: SubagentTranscript): string | null {
  const transcript = trace.transcript;
  if (!transcript) return null;
  for (let i = transcript.length - 1; i >= 0; i--) {
    const msg = transcript[i];
    if (msg.type === "tool") {
      // Latest activity is a completed tool result — no call in flight.
      return null;
    }
    if (msg.type === "ai" && msg.tool_calls && msg.tool_calls.length > 0) {
      const last = msg.tool_calls[msg.tool_calls.length - 1];
      return last.name;
    }
  }
  return null;
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
  onUploadFiles,
}: Props) {
  const [input, setInput] = useState("");
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
  const [traceWidth, setTraceWidth] = useState(520);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleAttachClick = () => fileInputRef.current?.click();
  const handleFilesChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await onUploadFiles(files);
    // Reset so picking the same file again re-fires onChange.
    e.target.value = "";
  };

  // Auto-grow the textarea to fit its content, up to CHAT_INPUT_MAX_PX.
  // Above the cap it becomes scrollable so a long paste doesn't push
  // the messages off-screen.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, CHAT_INPUT_MAX_PX)}px`;
  }, [input]);

  const handleTraceResize = useCallback((delta: number) => {
    setTraceWidth((w) => Math.min(900, Math.max(280, w - delta)));
  }, []);

  // Auto-scroll to bottom on new messages, but only when the user is
  // already near the bottom — otherwise every streamed token would yank
  // the viewport away from wherever they scrolled back to read.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom < 200) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
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

  // Memoise the item pipeline so the O(n) transforms don't re-run on
  // every render (input keystrokes, resize, trace toggle...) — a busy
  // transcript can otherwise cost noticeable frame time. syntheticTraces
  // used to depend on displayItems by identity but displayItems was
  // recomputed each render, so its useMemo never hit; keying it here
  // makes the memoisation actually stick.
  const rawItems = useMemo(() => buildDisplayItems(messages), [messages]);
  const displayItems = useMemo(
    () => collapseAgentRuns(rawItems, subagentStates),
    [rawItems, subagentStates],
  );
  const syntheticTraces = useMemo(
    () => buildSyntheticTraces(displayItems),
    [displayItems],
  );

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
                const isReporter = item.run.agentName === "reporter_agent";
                const finalResponse = isReporter ? extractFinalResponse(item.run.messages) : null;
                return (
                  <div key={item.run.syntheticId}>
                    <AgentRunCard
                      run={item.run}
                      onSelectTrace={handleSelectTrace}
                      isSelected={selectedTrace === item.run.syntheticId}
                    />
                    {finalResponse && <FinalAnswerBox content={finalResponse} />}
                  </div>
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
                    <AgentAvatar
                      name={trace.agent_name}
                      fallback={trace.avatar}
                      size={22}
                    />
                    <span className="subagent-card-name">{trace.agent_name}</span>
                    <span className="subagent-card-action">
                      <span className="live-dot" />
                      {selectedTrace === invId ? "Viewing live trace" : "View live trace"}
                    </span>
                  </div>
                  {(() => {
                    const currentToolCall = extractCurrentToolCall(trace);
                    if (!currentToolCall) return null;
                    return (
                      <div className="subagent-card-output">
                        <span className="tool-call-pill">→ {currentToolCall}</span>
                      </div>
                    );
                  })()}
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

          <div className="chat-input-shell">
          <form
            className="chat-input-bar"
            onSubmit={handleSubmit}
          >
            <textarea
              ref={textareaRef}
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRunning ? "Agent is running..." : "Ask the agent..."}
              disabled={isRunning}
              rows={1}
            />
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={handleFilesChosen}
            />
            <button
              type="button"
              className="chat-attach-button"
              onClick={handleAttachClick}
              disabled={isRunning}
              aria-label="Upload files to this project"
            >
              <svg
                viewBox="0 0 16 16"
                width="18"
                height="18"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              >
                <path d="M8 3v10M3 8h10" />
              </svg>
              <span className="chat-button-tooltip chat-button-tooltip-left" role="tooltip">
                Upload files to this project
              </span>
            </button>
            <button
              type="submit"
              className="chat-send-button"
              disabled={isRunning || !input.trim()}
              aria-label="Send message"
            >
              <svg
                viewBox="0 0 16 16"
                width="16"
                height="16"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M8 13V3M3.5 7.5L8 3l4.5 4.5" />
              </svg>
              <span className="chat-button-tooltip chat-button-tooltip-right" role="tooltip">
                {isRunning
                  ? "Agent is running"
                  : input.trim()
                    ? "Send message"
                    : "Type a message to send"}
              </span>
            </button>
          </form>
          </div>
        </div>
      </div>

      {activeTrace && (
        <>
          <ResizeDivider onResize={handleTraceResize} />
          <div className="chat-column-right" style={{ width: traceWidth, minWidth: 280 }}>
            <TracePanel
              state={activeTrace}
              onClose={() => setSelectedTrace(null)}
            />
          </div>
        </>
      )}
    </div>
  );
}
